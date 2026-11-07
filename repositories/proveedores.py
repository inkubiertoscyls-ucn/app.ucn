"""
Proveedores repository.

`rut_proveedor` es la clave primaria real: no existe `id_proveedor`.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from repositories.base import BaseRepository


class ProveedoresRepository(BaseRepository):
    def __init__(self):
        super().__init__("dim_proveedor")

    def get_activos(self) -> List[Dict]:
        """Proveedores activos."""
        return self.get_all({"activo": True})

    def get_by_rut_estricto(self, rut: str) -> Optional[Dict]:
        """Obtiene un proveedor por RUT sin ocultar errores de conexión."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("rut_proveedor", rut)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def buscar_estricto(self, termino: str) -> List[Dict]:
        """Busca por nombre, RUT, contacto o tipo y propaga errores."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .or_(
                "nombre_proveedor.ilike.%{0}%,"
                "rut_proveedor.ilike.%{0}%,"
                "contacto_proveedor.ilike.%{0}%,"
                "tipo_proveedor.ilike.%{0}%".format(termino)
            )
            .execute()
        )
        return response.data or []

    def existe_rut(self, rut: str) -> bool:
        """Indica si el RUT ya está registrado."""
        return self.get_by_rut_estricto(rut) is not None
