"""Repositorio de la dimensión fecha (solo lectura)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .base import BaseRepository


def _fecha_texto(valor: Any) -> Optional[str]:
    """Normaliza una fecha a YYYY-MM-DD para compararla con `dim_fecha`."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    return texto[:10] if texto else None


class FechasRepository(BaseRepository):
    def __init__(self):
        super().__init__("dim_fecha")

    def ids_por_fechas(self, fechas: Iterable[Any]) -> Dict[str, int]:
        """Devuelve {fecha ISO: id_fecha} para las fechas existentes.

        No crea fechas: la importación solo usa el calendario ya cargado y
        marca como error las fechas que no existen en `dim_fecha`.
        """
        normalizadas = sorted(
            {
                texto
                for texto in (_fecha_texto(valor) for valor in fechas or [])
                if texto
            }
        )
        resultado: Dict[str, int] = {}
        for inicio in range(0, len(normalizadas), 50):
            lote = normalizadas[inicio : inicio + 50]
            response = (
                self.client.table(self.table_name)
                .select("id_fecha, fecha")
                .in_("fecha", lote)
                .execute()
            )
            for fila in response.data or []:
                texto = _fecha_texto(fila.get("fecha"))
                if texto and fila.get("id_fecha") is not None:
                    resultado[texto] = fila.get("id_fecha")
        return resultado

    def rango_ids(
        self,
        desde: Optional[str] = None,
        hasta: Optional[str] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Devuelve los ids de fecha que cubren un rango inclusivo.

        Retorna (None, None) si no existe ninguna fecha en el rango, lo que
        significa que tampoco puede haber movimientos en ese período.
        """
        desde_texto = str(desde) if desde else None
        hasta_texto = str(hasta) if hasta else None

        primera_query = self.client.table(self.table_name).select("id_fecha, fecha")
        ultima_query = self.client.table(self.table_name).select("id_fecha, fecha")
        if desde_texto:
            primera_query = primera_query.gte("fecha", desde_texto)
            ultima_query = ultima_query.gte("fecha", desde_texto)
        if hasta_texto:
            primera_query = primera_query.lte("fecha", hasta_texto)
            ultima_query = ultima_query.lte("fecha", hasta_texto)

        primera = primera_query.order("fecha").limit(1).execute()
        ultima = ultima_query.order("fecha", desc=True).limit(1).execute()
        filas_primera = primera.data or []
        filas_ultima = ultima.data or []
        if not filas_primera or not filas_ultima:
            return None, None
        return (
            filas_primera[0].get("id_fecha"),
            filas_ultima[0].get("id_fecha"),
        )
