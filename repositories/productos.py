"""
Productos repository.
"""
from typing import List, Dict, Optional
from .base import BaseRepository
from core.exceptions import DuplicateError, ValidationError


class ProductosRepository(BaseRepository):
    def __init__(self):
        super().__init__("dim_producto")
    
    def get_activos(self) -> List[Dict]:
        """Get active products."""
        return self.get_all({"activo": True})
    
    def get_by_id_estricto(self, id_producto: int) -> Optional[Dict]:
        """Obtiene un producto por ID sin ocultar errores de conexión."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("id_producto", id_producto)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_by_nombre(self, nombre: str) -> Optional[Dict]:
        """Get product by name."""
        try:
            return self.get_by_nombre_estricto(nombre)
        except Exception:
            return None

    def get_by_nombre_estricto(self, nombre: str) -> Optional[Dict]:
        """Busca por nombre exacto sin ocultar errores de conexión."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .ilike("nombre_producto", nombre)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    
    def buscar_estricto(self, termino: str) -> List[Dict]:
        """Busca productos y propaga errores de conexión o esquema.

        Se separa de `buscar` para que la capa de datos pueda distinguir una
        búsqueda vacía de un fallo real.
        """
        response = self.client.table(self.table_name).select("*").or_(
            f"nombre_producto.ilike.%{termino}%,categoria.ilike.%{termino}%"
        ).execute()
        return response.data or []

    def buscar(self, termino: str) -> List[Dict]:
        """Search products by name or category."""
        try:
            return self.buscar_estricto(termino)
        except Exception:
            return []
    
    def existe_nombre(self, nombre: str, exclude_id: int = None) -> bool:
        """Check if product name exists."""
        producto = self.get_by_nombre_estricto(nombre)
        if not producto:
            return False
        if exclude_id and producto.get("id_producto") == exclude_id:
            return False
        return True
