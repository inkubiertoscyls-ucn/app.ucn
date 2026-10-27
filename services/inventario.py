"""
Inventario service - Business logic for inventory movements.
Priority: stock calculation from history, validations, permissions.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

from repositories.movimientos import MovimientosRepository
from repositories.productos import ProductosRepository
from repositories.usuarios import UsuariosRepository
from repositories.base import BaseRepository
from core.exceptions import (
    ValidationError, 
    InventoryError, 
    NegativeStockError, 
    NotFoundError,
    AuthorizationError
)
from core.utils import normalizar_rut, validar_rut, es_numero_positivo

logger = logging.getLogger(__name__)


class InventarioService:
    def __init__(self):
        self.movimientos_repo = MovimientosRepository()
        self.productos_repo = ProductosRepository()
        self.usuarios_repo = UsuariosRepository()
        self.areas_repo = BaseRepository("dim_area")
        self.tipos_mov_repo = BaseRepository("dim_tipo_movimiento")
        self.proveedores_repo = BaseRepository("dim_proveedor")
        self.eventos_repo = BaseRepository("dim_evento")
        self.fechas_repo = BaseRepository("dim_fecha")
    
    def calcular_stock_actual(self, id_producto: int, id_area: int) -> int:
        """
        Calculate current stock from movement history.
        Stock = sum(cantidad * factor_stock) for all movements.
        No stock stored separately.
        """
        try:
            movimientos = self.movimientos_repo.get_stock_movimientos(id_producto, id_area)
            stock = 0
            for mov in movimientos:
                cantidad = mov.get("cantidad", 0)
                tipo_mov = mov.get("dim_tipo_movimiento", {})
                factor = tipo_mov.get("factor_stock", 0) if tipo_mov else 0
                stock += cantidad * factor
            return stock
        except Exception as e:
            logger.error(f"Error calculating stock: {type(e).__name__}")
            return 0
    
    def productos_bajo_stock_minimo(self, id_area: int = None) -> List[Dict]:
        """Identify products below minimum stock."""
        try:
            productos = self.productos_repo.get_activos()
            resultado = []
            for prod in productos:
                id_producto = prod["id_producto"]
                stock_minimo = prod.get("stock_minimo", 0)
                # Calculate stock across all areas or specific area
                if id_area:
                    stock_actual = self.calcular_stock_actual(id_producto, id_area)
                    if stock_actual < stock_minimo:
                        resultado.append({
                            **prod,
                            "stock_actual": stock_actual,
                            "area": id_area,
                            "bajo_minimo": True
                        })
                else:
                    # Check all areas where product has movements
                    movimientos = self.movimientos_repo.get_by_producto(id_producto)
                    areas = set(m["id_area"] for m in movimientos)
                    for area_id in areas:
                        stock_actual = self.calcular_stock_actual(id_producto, area_id)
                        if stock_actual < stock_minimo:
                            resultado.append({
                                **prod,
                                "stock_actual": stock_actual,
                                "id_area": area_id,
                                "bajo_minimo": True
                            })
            return resultado
        except Exception as e:
            logger.error(f"Error finding low stock: {type(e).__name__}")
            return []
    
    def _validar_movimiento_base(self, data: Dict) -> None:
        """Validate base movement data."""
        # Validate required fields
        required = ["id_producto", "id_area", "id_tipo_movimiento", "rut_usuario", "cantidad"]
        for field in required:
            if field not in data or data[field] is None:
                raise ValidationError(f"Campo requerido: {field}")
        
        # Validate quantity positive
        if not es_numero_positivo(data["cantidad"]):
            raise ValidationError("La cantidad debe ser un número positivo")
        
        # Validate RUT
        try:
            rut_norm = normalizar_rut(data["rut_usuario"])
            if not validar_rut(rut_norm):
                raise ValidationError("RUT de usuario inválido")
            data["rut_usuario"] = rut_norm
        except Exception as e:
            raise ValidationError(f"RUT inválido: {e}")
        
        # Validate user exists and is active
        usuario = self.usuarios_repo.get_by_rut(data["rut_usuario"])
        if not usuario:
            raise NotFoundError("Usuario no encontrado")
        if not usuario.get("activo", False):
            raise AuthorizationError("Usuario inactivo no puede registrar movimientos")
        
        # Validate product exists and active
        producto = self.productos_repo.get_by_id("id_producto", data["id_producto"])
        if not producto:
            raise NotFoundError("Producto no encontrado")
        if not producto.get("activo", False):
            raise ValidationError("Producto inactivo")
        
        # Validate area exists
        area = self.areas_repo.get_by_id("id_area", data["id_area"])
        if not area:
            raise NotFoundError("Área no encontrada")
        
        # Validate movement type exists
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if not tipo_mov:
            raise NotFoundError("Tipo de movimiento no encontrado")
        if not tipo_mov.get("activo", False):
            raise ValidationError("Tipo de movimiento inactivo")
        
        # Validate optional provider
        if data.get("rut_proveedor"):
            try:
                rut_prov_norm = normalizar_rut(data["rut_proveedor"])
                if not validar_rut(rut_prov_norm):
                    raise ValidationError("RUT de proveedor inválido")
                proveedor = self.proveedores_repo.get_by_id("rut_proveedor", rut_prov_norm)
                if not proveedor:
                    raise NotFoundError("Proveedor no encontrado")
                data["rut_proveedor"] = rut_prov_norm
            except Exception as e:
                if isinstance(e, (ValidationError, NotFoundError)):
                    raise
                raise ValidationError(f"RUT de proveedor inválido: {e}")
        
        # Validate optional event
        if data.get("id_evento"):
            evento = self.eventos_repo.get_by_id("id_evento", data["id_evento"])
            if not evento:
                raise NotFoundError("Evento no encontrado")
    
    def registrar_entrada(self, data: Dict) -> Dict:
        """Register product entry (purchase)."""
        self._validar_movimiento_base(data)
        # Get movement type with factor +1
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if tipo_mov.get("factor_stock") != 1:
            raise ValidationError("Tipo de movimiento debe tener factor_stock +1 para entrada")
        
        # Add fecha
        if not data.get("id_fecha"):
            hoy = datetime.now().date()
            fecha = self.fechas_repo.get_all({"fecha": str(hoy)})
            if fecha:
                data["id_fecha"] = fecha[0]["id_fecha"]
            else:
                # Create if not exists
                created = self.fechas_repo.create({
                    "fecha": str(hoy),
                    "dia": hoy.day,
                    "mes": hoy.month,
                    "anio": hoy.year
                })
                data["id_fecha"] = created["id_fecha"]
        
        data["fecha_hora_registro"] = datetime.now().isoformat()
        return self.movimientos_repo.create(data)
    
    def registrar_salida(self, data: Dict, permitir_negativo: bool = False) -> Dict:
        """Register product exit."""
        self._validar_movimiento_base(data)
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if tipo_mov.get("factor_stock") != -1:
            raise ValidationError("Tipo de movimiento debe tener factor_stock -1 para salida")
        
        # Check stock
        if not permitir_negativo:
            stock_actual = self.calcular_stock_actual(data["id_producto"], data["id_area"])
            cantidad = int(data["cantidad"])
            if stock_actual - cantidad < 0:
                raise NegativeStockError(
                    f"Stock insuficiente. Actual: {stock_actual}, Solicitado: {cantidad}"
                )
        
        if not data.get("id_fecha"):
            hoy = datetime.now().date()
            fecha = self.fechas_repo.get_all({"fecha": str(hoy)})
            if fecha:
                data["id_fecha"] = fecha[0]["id_fecha"]
            else:
                created = self.fechas_repo.create({
                    "fecha": str(hoy),
                    "dia": hoy.day,
                    "mes": hoy.month,
                    "anio": hoy.year
                })
                data["id_fecha"] = created["id_fecha"]
        
        data["fecha_hora_registro"] = datetime.now().isoformat()
        return self.movimientos_repo.create(data)
    
    def registrar_merma(self, data: Dict, permitir_negativo: bool = False) -> Dict:
        """Register loss/waste."""
        self._validar_movimiento_base(data)
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if tipo_mov.get("factor_stock") != -1:
            raise ValidationError("Tipo de movimiento debe tener factor_stock -1 para merma")
        
        if not permitir_negativo:
            stock_actual = self.calcular_stock_actual(data["id_producto"], data["id_area"])
            cantidad = int(data["cantidad"])
            if stock_actual - cantidad < 0:
                raise NegativeStockError(
                    f"Stock insuficiente para merma. Actual: {stock_actual}, Solicitado: {cantidad}"
                )
        
        if not data.get("id_fecha"):
            hoy = datetime.now().date()
            fecha = self.fechas_repo.get_all({"fecha": str(hoy)})
            if fecha:
                data["id_fecha"] = fecha[0]["id_fecha"]
            else:
                created = self.fechas_repo.create({
                    "fecha": str(hoy),
                    "dia": hoy.day,
                    "mes": hoy.month,
                    "anio": hoy.year
                })
                data["id_fecha"] = created["id_fecha"]
        
        data["fecha_hora_registro"] = datetime.now().isoformat()
        return self.movimientos_repo.create(data)
    
    def registrar_ajuste_positivo(self, data: Dict) -> Dict:
        """Register positive adjustment."""
        self._validar_movimiento_base(data)
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if tipo_mov.get("factor_stock") != 1:
            raise ValidationError("Tipo de movimiento debe tener factor_stock +1 para ajuste positivo")
        
        if not data.get("id_fecha"):
            hoy = datetime.now().date()
            fecha = self.fechas_repo.get_all({"fecha": str(hoy)})
            if fecha:
                data["id_fecha"] = fecha[0]["id_fecha"]
            else:
                created = self.fechas_repo.create({
                    "fecha": str(hoy),
                    "dia": hoy.day,
                    "mes": hoy.month,
                    "anio": hoy.year
                })
                data["id_fecha"] = created["id_fecha"]
        
        data["fecha_hora_registro"] = datetime.now().isoformat()
        return self.movimientos_repo.create(data)
    
    def registrar_ajuste_negativo(self, data: Dict, permitir_negativo: bool = False) -> Dict:
        """Register negative adjustment."""
        self._validar_movimiento_base(data)
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if tipo_mov.get("factor_stock") != -1:
            raise ValidationError("Tipo de movimiento debe tener factor_stock -1 para ajuste negativo")
        
        if not permitir_negativo:
            stock_actual = self.calcular_stock_actual(data["id_producto"], data["id_area"])
            cantidad = int(data["cantidad"])
            if stock_actual - cantidad < 0:
                raise NegativeStockError(
                    f"Stock insuficiente para ajuste negativo. Actual: {stock_actual}, Solicitado: {cantidad}"
                )
        
        if not data.get("id_fecha"):
            hoy = datetime.now().date()
            fecha = self.fechas_repo.get_all({"fecha": str(hoy)})
            if fecha:
                data["id_fecha"] = fecha[0]["id_fecha"]
            else:
                created = self.fechas_repo.create({
                    "fecha": str(hoy),
                    "dia": hoy.day,
                    "mes": hoy.month,
                    "anio": hoy.year
                })
                data["id_fecha"] = created["id_fecha"]
        
        data["fecha_hora_registro"] = datetime.now().isoformat()
        return self.movimientos_repo.create(data)
    
    def consultar_historial(self, filtros: Dict = None) -> List[Dict]:
        """Query movement history with filters."""
        if filtros is None:
            filtros = {}
        return self.movimientos_repo.filtrar(
            id_producto=filtros.get("id_producto"),
            id_area=filtros.get("id_area"),
            id_tipo_movimiento=filtros.get("id_tipo_movimiento"),
            rut_usuario=filtros.get("rut_usuario"),
            id_fecha_desde=filtros.get("id_fecha_desde"),
            id_fecha_hasta=filtros.get("id_fecha_hasta")
        )
    
    def consultar_stock_por_producto_area(self, id_producto: int, id_area: int) -> Dict:
        """Get stock for product and area."""
        stock_actual = self.calcular_stock_actual(id_producto, id_area)
        producto = self.productos_repo.get_by_id("id_producto", id_producto)
        return {
            "id_producto": id_producto,
            "id_area": id_area,
            "stock_actual": stock_actual,
            "stock_minimo": producto.get("stock_minimo", 0) if producto else 0,
            "stock_maximo": producto.get("stock_maximo", 0) if producto else 0,
            "bajo_minimo": stock_actual < (producto.get("stock_minimo", 0) if producto else 0)
        }
    
    def verificar_permisos_movimiento(self, rut_usuario: str, rol_requerido: str = None) -> bool:
        """Check if user has permissions to register movements."""
        usuario = self.usuarios_repo.get_by_rut(rut_usuario)
        if not usuario:
            return False
        if not usuario.get("activo", False):
            return False
        if rol_requerido:
            return usuario.get("rol") == rol_requerido
        return usuario.get("rol") in ["Administrador", "Operario"]
