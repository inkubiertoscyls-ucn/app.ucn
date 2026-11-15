"""Fecha y hora oficiales de la aplicación (zona horaria de Chile).

El servidor donde corre Streamlit puede estar en UTC (por ejemplo Streamlit
Cloud). Todas las marcas de tiempo y la fecha "de hoy" se calculan siempre en
America/Santiago para que el registro no dependa de la máquina.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")


def ahora_chile() -> datetime:
    """Fecha y hora actual en Chile, con zona horaria."""
    return datetime.now(ZONA_CHILE)


def hoy_chile() -> date:
    """Fecha de hoy en Chile."""
    return ahora_chile().date()


def marca_tiempo() -> str:
    """Marca de tiempo ISO con desfase horario, lista para guardar en BD.

    Con columnas `TIMESTAMP` Postgres conserva la hora local de Chile; con
    `TIMESTAMPTZ` convierte correctamente gracias al desfase incluido.
    """
    return ahora_chile().isoformat(timespec="seconds")


def a_hora_chile(valor: datetime) -> datetime:
    """Convierte una fecha con zona horaria a la hora de Chile.

    Las fechas sin zona horaria se consideran ya expresadas en hora de Chile,
    que es como las guarda la aplicación.
    """
    if valor.tzinfo is None:
        return valor
    return valor.astimezone(ZONA_CHILE)
