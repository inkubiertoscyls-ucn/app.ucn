"""Catálogo de tipos de evento, sin acceso a datos.

`dim_evento.tipo_evento` tiene en Supabase la restricción
`dim_evento_tipo_evento_check`, que solo acepta estos valores exactos
(con tildes y mayúsculas). Si se cambia la restricción en la base, hay que
actualizar esta lista.
"""
from __future__ import annotations

TIPOS_EVENTO = (
    "Música en Vivo",
    "Stand-up Comedy",
    "Noche Temática",
    "Jornada Normal",
    "Otro tipo",
)


def tipos_evento_texto() -> str:
    """Lista legible de los tipos permitidos: 'A, B, ... o E'."""
    return ", ".join(TIPOS_EVENTO[:-1]) + " o " + TIPOS_EVENTO[-1]
