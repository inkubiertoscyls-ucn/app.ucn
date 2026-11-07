"""Marcadores de importación de inventario.

`hecho_inventario` no tiene columnas para el archivo de origen ni para el
documento. Para no inventar columnas, el marcador y el documento se guardan
dentro de `observacion` con un formato explícito y reversible.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

PREFIJO_MARCADOR = "[INK-IMPORT:"
PATRON_MARCADOR = re.compile(
    r"\s*\[INK-IMPORT:([0-9a-f]{64}):(\d+)\]"
)


def crear_marcador(hash_archivo: str, fila: int) -> str:
    """Marca única de una fila de un archivo concreto."""
    return f"{PREFIJO_MARCADOR}{hash_archivo}:{int(fila)}]"


def marcador_de(observacion: object) -> Optional[Tuple[str, int]]:
    """Extrae (hash de archivo, fila) del marcador, si existe."""
    coincidencia = PATRON_MARCADOR.search(str(observacion or ""))
    if not coincidencia:
        return None
    return coincidencia.group(1), int(coincidencia.group(2))


def quitar_marcador(observacion: object) -> str:
    """Devuelve la observación visible, sin el marcador técnico."""
    return PATRON_MARCADOR.sub("", str(observacion or "")).strip()


def componer_observacion(
    marcador: str,
    documento: str = "",
    observacion: str = "",
) -> str:
    """Une marcador, documento y observación en el campo existente."""
    partes = [str(marcador or "").strip()]
    documento_texto = str(documento or "").strip()
    if documento_texto:
        partes.append(f"Documento: {documento_texto}")
    observacion_texto = str(observacion or "").strip()
    if observacion_texto:
        partes.append(observacion_texto)
    return " · ".join(parte for parte in partes if parte)
