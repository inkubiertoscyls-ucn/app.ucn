"""
Inventario service - Business logic for inventory movements.
Priority: stock calculation from history, validations, permissions.
"""
import logging
import math
from typing import Dict, List

from repositories.movimientos import MovimientosRepository
from repositories.productos import ProductosRepository
from repositories.usuarios import UsuariosRepository
from repositories.base import BaseRepository
from core.tiempo import hoy_chile, marca_tiempo
from core.exceptions import (
    ValidationError,
    NegativeStockError,
    NotFoundError,
    AuthorizationError,
)
from core.utils import normalizar_rut, validar_rut, es_numero_positivo
from core.stock import calcular_stock

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

    def calcular_stock_actual(self, id_producto: int, id_area: int) -> float:
        """
        Calculate current stock from movement history.
        Stock = sum(cantidad * factor_stock) for all movements.
        No stock stored separately.

        Los errores de conexión se propagan: un stock 0 inventado podría
        bloquear salidas válidas o mostrar alertas falsas.
        """
        try:
            movimientos = self.movimientos_repo.get_stock_movimientos(id_producto, id_area)
        except Exception as e:
            logger.error("Error calculating stock: %s", type(e).__name__)
            raise
        return calcular_stock(movimientos)

    def _resolver_costo_unitario(self, data: Dict, producto: Dict) -> float:
        """Resuelve el costo unitario obligatorio de `hecho_inventario`.

        Si el formulario no lo informa se usa `costo_base` del producto y, como
        último respaldo, 0. Un valor informado debe ser numérico y no negativo.
        """
        valor = data.get("costo_unitario")
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            valor = producto.get("costo_base")
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            valor = 0

        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El costo unitario debe ser un número") from exc
        if not math.isfinite(numero) or numero < 0:
            raise ValidationError("El costo unitario no puede ser negativo")
        return numero

    def _resolver_id_fecha(self, data: Dict) -> int:
        """Resuelve la fecha del movimiento, creándola solo si no existe."""
        if data.get("id_fecha"):
            return data["id_fecha"]

        hoy = hoy_chile()
        fecha = self.fechas_repo.get_all({"fecha": str(hoy)})
        if fecha:
            data["id_fecha"] = fecha[0]["id_fecha"]
            return data["id_fecha"]

        created = self.fechas_repo.create(
            {
                "fecha": str(hoy),
                "dia": hoy.day,
                "mes": hoy.month,
                "anio": hoy.year,
            }
        )
        data["id_fecha"] = created["id_fecha"]
        return data["id_fecha"]

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
        # `hecho_inventario.cantidad` es INTEGER en la base de datos.
        if not float(data["cantidad"]).is_integer():
            raise ValidationError("La cantidad debe ser un número entero")

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

        # `hecho_inventario.costo_unitario` es obligatorio en la base real.
        data["costo_unitario"] = self._resolver_costo_unitario(data, producto)

        # Validate optional date identifier
        if data.get("id_fecha"):
            fecha = self.fechas_repo.get_all({"id_fecha": data["id_fecha"]})
            if not fecha:
                raise NotFoundError("Fecha no encontrada")

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
            except ValidationError as e:
                raise ValidationError(f"RUT de proveedor inválido: {e}") from e
            if not validar_rut(rut_prov_norm):
                raise ValidationError("RUT de proveedor inválido")
            # Un error de conexión aquí se propaga tal cual (no es un RUT inválido).
            proveedor = self.proveedores_repo.get_by_id("rut_proveedor", rut_prov_norm)
            if not proveedor:
                raise NotFoundError("Proveedor no encontrado")
            data["rut_proveedor"] = rut_prov_norm
        
        # Validate optional event
        if data.get("id_evento"):
            evento = self.eventos_repo.get_by_id("id_evento", data["id_evento"])
            if not evento:
                raise NotFoundError("Evento no encontrado")
    
    def _registrar(
        self,
        data: Dict,
        factor_esperado: int,
        descripcion: str,
        permitir_negativo: bool = False,
    ) -> Dict:
        """Valida y registra un movimiento con el factor de stock indicado.

        Para movimientos que descuentan stock se valida antes de insertar y se
        vuelve a comprobar después: si otro usuario registró una salida al
        mismo tiempo y el stock quedó negativo, el movimiento se revierte.
        """
        self._validar_movimiento_base(data)
        tipo_mov = self.tipos_mov_repo.get_by_id("id_tipo_movimiento", data["id_tipo_movimiento"])
        if tipo_mov.get("factor_stock") != factor_esperado:
            signo = "+1" if factor_esperado > 0 else "-1"
            raise ValidationError(
                f"Tipo de movimiento debe tener factor_stock {signo} para {descripcion}"
            )

        controlar_stock = factor_esperado < 0 and not permitir_negativo
        cantidad = float(data["cantidad"])
        if controlar_stock:
            self._exigir_stock(data, cantidad, descripcion)

        self._resolver_id_fecha(data)
        data["fecha_hora_registro"] = marca_tiempo()
        creado = self.movimientos_repo.create(data)

        if controlar_stock:
            self._verificar_tras_registro(data, creado, descripcion)
        return creado

    def _exigir_stock(self, data: Dict, cantidad: float, descripcion: str) -> None:
        stock_actual = self.calcular_stock_actual(data["id_producto"], data["id_area"])
        if stock_actual - cantidad < 0:
            raise NegativeStockError(
                f"Stock insuficiente para {descripcion}. "
                f"Actual: {stock_actual:g}, Solicitado: {cantidad:g}"
            )

    def _verificar_tras_registro(self, data: Dict, creado: Dict, descripcion: str) -> None:
        """Revierte el movimiento si un registro simultáneo dejó stock negativo."""
        stock_final = self.calcular_stock_actual(data["id_producto"], data["id_area"])
        if stock_final >= 0:
            return
        id_movimiento = (creado or {}).get("id_hecho_inventario")
        if id_movimiento is not None:
            self.movimientos_repo.delete("id_hecho_inventario", id_movimiento)
        raise NegativeStockError(
            f"Stock insuficiente para {descripcion}: otro usuario registró un "
            "movimiento del mismo producto al mismo tiempo. Revisa el stock e "
            "inténtalo nuevamente."
        )

    def registrar_entrada(self, data: Dict) -> Dict:
        """Register product entry (purchase)."""
        return self._registrar(data, 1, "entrada")

    def registrar_salida(self, data: Dict, permitir_negativo: bool = False) -> Dict:
        """Register product exit."""
        return self._registrar(data, -1, "salida", permitir_negativo)

    def registrar_merma(self, data: Dict, permitir_negativo: bool = False) -> Dict:
        """Register loss/waste."""
        return self._registrar(data, -1, "merma", permitir_negativo)

    def registrar_ajuste_positivo(self, data: Dict) -> Dict:
        """Register positive adjustment."""
        return self._registrar(data, 1, "ajuste positivo")

    def registrar_ajuste_negativo(self, data: Dict, permitir_negativo: bool = False) -> Dict:
        """Register negative adjustment."""
        return self._registrar(data, -1, "ajuste negativo", permitir_negativo)

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
