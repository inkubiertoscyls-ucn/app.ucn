"""
Productos service - Business logic for products.
"""
from typing import List, Dict, Optional
from repositories.productos import ProductosRepository
from core.exceptions import ValidationError, DuplicateError, NotFoundError
from core.utils import es_numero_no_negativo


class ProductosService:
    def __init__(self):
        self.repo = ProductosRepository()
    
    def listar_productos(self, solo_activos: bool = True) -> List[Dict]:
        """List products."""
        if solo_activos:
            return self.repo.get_activos()
        return self.repo.get_all()
    
    def consultar_producto(self, id_producto: int) -> Optional[Dict]:
        """Get product by ID."""
        return self.repo.get_by_id("id_producto", id_producto)
    
    def registrar_producto(self, data: Dict) -> Dict:
        """Register new product."""
        self._validar_producto(data)
        if self.repo.existe_nombre(data["nombre_producto"]):
            raise DuplicateError("Ya existe un producto con ese nombre")
        return self.repo.create(data)
    
    def modificar_producto(self, id_producto: int, data: Dict) -> Dict:
        """Modify product."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")
        if "nombre_producto" in data:
            self._validar_nombre(data["nombre_producto"])
            if self.repo.existe_nombre(data["nombre_producto"], exclude_id=id_producto):
                raise DuplicateError("Ya existe un producto con ese nombre")
        if "costo_base" in data and not es_numero_no_negativo(data["costo_base"]):
            raise ValidationError("El costo base no puede ser negativo")
        if "stock_minimo" in data and int(data["stock_minimo"]) < 0:
            raise ValidationError("El stock mínimo no puede ser negativo")
        if "stock_maximo" in data and int(data["stock_maximo"]) < 0:
            raise ValidationError("El stock máximo no puede ser negativo")
        return self.repo.update("id_producto", id_producto, data)
    
    def desactivar_producto(self, id_producto: int) -> Dict:
        """Deactivate product without deleting history."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")
        return self.repo.deactivate("id_producto", id_producto)
    
    def consultar_stock_min_max(self, id_producto: int) -> Dict:
        """Get min and max stock configured."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")
        return {
            "id_producto": id_producto,
            "stock_minimo": producto.get("stock_minimo", 0),
            "stock_maximo": producto.get("stock_maximo", 0)
        }
    
    def buscar_productos(self, termino: str) -> List[Dict]:
        """Search products by name or category."""
        if not termino or len(termino.strip()) < 2:
            raise ValidationError("Término de búsqueda debe tener al menos 2 caracteres")
        return self.repo.buscar(termino.strip())
    
    def _validar_producto(self, data: Dict) -> None:
        """Validate product data."""
        if not data.get("nombre_producto") or not str(data["nombre_producto"]).strip():
            raise ValidationError("El nombre del producto es requerido")
        self._validar_nombre(data["nombre_producto"])
        if not data.get("unidad_medida"):
            raise ValidationError("La unidad de medida es requerida")
        if "costo_base" in data and not es_numero_no_negativo(data["costo_base"]):
            raise ValidationError("El costo base no puede ser negativo")
        if "stock_minimo" in data and int(data["stock_minimo"]) < 0:
            raise ValidationError("El stock mínimo no puede ser negativo")
        if "stock_maximo" in data and int(data["stock_maximo"]) < 0:
            raise ValidationError("El stock máximo no puede ser negativo")
    
    def _validar_nombre(self, nombre: str) -> None:
        """Validate product name."""
        nombre = str(nombre).strip()
        if len(nombre) < 2:
            raise ValidationError("El nombre del producto debe tener al menos 2 caracteres")
        if len(nombre) > 150:
            raise ValidationError("El nombre del producto no puede exceder 150 caracteres")
