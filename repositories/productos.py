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
    
    def get_by_nombre(self, nombre: str) -> Optional[Dict]:
        """Get product by name."""
        try:
            response = self.client.table(self.table_name).select("*").ilike("nombre_producto", nombre).execute()
            return response.data[0] if response.data else None
        except Exception:
            return None
    
    def buscar(self, termino: str) -> List[Dict]:
        """Search products by name or category."""
        try:
            response = self.client.table(self.table_name).select("*").or_(
                f"nombre_producto.ilike.%{termino}%,categoria.ilike.%{termino}%"
            ).execute()
            return response.data or []
        except Exception:
            return []
    
    def existe_nombre(self, nombre: str, exclude_id: int = None) -> bool:
        """Check if product name exists."""
        producto = self.get_by_nombre(nombre)
        if not producto:
            return False
        if exclude_id and producto.get("id_producto") == exclude_id:
            return False
        return True
