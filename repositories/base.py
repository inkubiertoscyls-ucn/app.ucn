"""
Base repository with common CRUD operations.
"""
from typing import Dict, List, Any, Optional
from db.supabase_client import get_supabase_client
from core.exceptions import DuplicateError


class BaseRepository:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.client = get_supabase_client()
    
    def get_all(self, filters: Dict = None) -> List[Dict]:
        """Get all records with optional filters."""
        query = self.client.table(self.table_name).select("*")
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        response = query.execute()
        return response.data or []
    
    def get_by_id(self, id_column: str, id_value: Any) -> Optional[Dict]:
        """Get record by ID.

        Devuelve None solo si el registro no existe. Los errores de conexión
        se propagan para no confundirlos con "no encontrado".
        """
        response = self.client.table(self.table_name).select("*").eq(id_column, id_value).execute()
        return response.data[0] if response.data else None
    
    def create(self, data: Dict) -> Dict:
        """Create record."""
        try:
            response = self.client.table(self.table_name).insert(data).execute()
            return response.data[0] if response.data else data
        except Exception as e:
            if "duplicate" in str(e).lower():
                raise DuplicateError(f"Registro duplicado en {self.table_name}")
            raise
    
    def update(self, id_column: str, id_value: Any, data: Dict) -> Dict:
        """Update record."""
        response = self.client.table(self.table_name).update(data).eq(id_column, id_value).execute()
        return response.data[0] if response.data else data
    
    def delete(self, id_column: str, id_value: Any) -> bool:
        """Delete record (use with caution).

        Devuelve True si se eliminó al menos un registro. Los errores se
        propagan para que quien llama sepa por qué falló.
        """
        response = self.client.table(self.table_name).delete().eq(id_column, id_value).execute()
        return bool(response.data)
    
    def deactivate(self, id_column: str, id_value: Any) -> Dict:
        """Deactivate record (soft delete)."""
        return self.update(id_column, id_value, {"activo": False})
