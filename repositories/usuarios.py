"""
Usuarios repository.
"""
from typing import List, Dict, Optional
from .base import BaseRepository
from core.utils import normalizar_rut, validar_rut
from core.exceptions import InvalidRUTError


class UsuariosRepository(BaseRepository):
    def __init__(self):
        super().__init__("dim_usuario")
    
    def get_by_rut(self, rut: str) -> Optional[Dict]:
        """Get user by RUT (PK)."""
        try:
            rut_norm = normalizar_rut(rut)
            if not validar_rut(rut_norm):
                raise InvalidRUTError("RUT inválido")
            return self.get_by_id("rut_usuario", rut_norm)
        except InvalidRUTError:
            raise
        except Exception:
            return None
    
    def get_activos(self) -> List[Dict]:
        """Get active users."""
        return self.get_all({"activo": True})
    
    def get_by_rol(self, rol: str) -> List[Dict]:
        """Get users by role."""
        return self.get_all({"rol": rol})

    def nombres_por_rut(self) -> List[Dict]:
        """Devuelve solo RUT y nombre, sin datos sensibles.

        Se usa para mostrar al responsable de un movimiento en el historial.
        """
        response = (
            self.client.table(self.table_name)
            .select("rut_usuario, nombre_usuario")
            .execute()
        )
        return response.data or []
    
    def es_activo(self, rut: str) -> bool:
        """Check if user is active."""
        usuario = self.get_by_rut(rut)
        if not usuario:
            return False
        return usuario.get("activo", False)
    
    def es_administrador(self, rut: str) -> bool:
        """Check if user is admin."""
        usuario = self.get_by_rut(rut)
        if not usuario:
            return False
        return usuario.get("activo", False) and usuario.get("rol") == "Administrador"
    
    def es_operario(self, rut: str) -> bool:
        """Check if user is operator."""
        usuario = self.get_by_rut(rut)
        if not usuario:
            return False
        return usuario.get("activo", False) and usuario.get("rol") == "Operario"
