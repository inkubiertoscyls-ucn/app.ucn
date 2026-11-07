"""Repositorio del catálogo de eventos y artistas.

`dim_evento` guarda el nombre del evento y el nombre del artista en la misma
fila: no existe una tabla separada de artistas. `id_evento` es la clave real.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories.base import BaseRepository


def _fecha_texto(valor: Any) -> Optional[str]:
    """Normaliza una fecha de Supabase a texto ISO para poder compararla."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto[:10] if texto else None


class EventosRepository(BaseRepository):
    def __init__(self):
        super().__init__("dim_evento")

    def get_activos(self) -> List[Dict]:
        """Eventos activos."""
        return self.get_all({"activo": True})

    def get_by_id_estricto(self, id_evento: int) -> Optional[Dict]:
        """Obtiene un evento por ID sin ocultar errores de conexión."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("id_evento", id_evento)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def buscar_estricto(self, termino: str) -> List[Dict]:
        """Busca por evento, artista o tipo y propaga errores."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .or_(
                "nombre_evento.ilike.%{0}%,"
                "nombre_artista.ilike.%{0}%,"
                "tipo_evento.ilike.%{0}%".format(termino)
            )
            .execute()
        )
        return response.data or []

    def _fechas_de_tabla(
        self,
        tabla: str,
        campo_fecha: str,
        campo_orden: str,
        tamano_pagina: int = 1000,
    ) -> List[Dict]:
        """Lee `id_evento` y fecha de una tabla, paginando el resultado."""
        tamano = max(1, int(tamano_pagina))
        filas: List[Dict] = []
        inicio = 0

        while True:
            response = (
                self.client.table(tabla)
                .select(f"id_evento, {campo_fecha}")
                .order(campo_orden, desc=False)
                .range(inicio, inicio + tamano - 1)
                .execute()
            )
            lote = response.data or []
            filas.extend(lote)
            if len(lote) < tamano:
                break
            inicio += tamano

        return filas

    def fechas_actividad(self) -> Dict[int, Dict[str, str]]:
        """Deriva la primera y última fecha de actividad por evento.

        Usa solo ventas y movimientos ya vinculados a un evento. No crea ni
        modifica relaciones ni fechas.
        """
        actividad: Dict[int, Dict[str, str]] = {}

        fuentes = (
            ("hecho_venta_fudo", "fecha_venta", "id_venta_fudo"),
            ("hecho_inventario", "fecha_hora_registro", "id_hecho_inventario"),
        )
        for tabla, campo_fecha, campo_orden in fuentes:
            for fila in self._fechas_de_tabla(tabla, campo_fecha, campo_orden):
                try:
                    id_evento = int(fila.get("id_evento"))
                except (TypeError, ValueError):
                    continue
                fecha = _fecha_texto(fila.get(campo_fecha))
                if not fecha:
                    continue

                registro = actividad.setdefault(id_evento, {})
                if "primera" not in registro or fecha < registro["primera"]:
                    registro["primera"] = fecha
                if "ultima" not in registro or fecha > registro["ultima"]:
                    registro["ultima"] = fecha

        return actividad
