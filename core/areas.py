"""Normalización de áreas sin acceso a datos.

`dim_usuario.area_asignada` es texto libre en la base real (por ejemplo
'Todas'), por lo que se aceptan nombres o ids sin convertir ni modificar la
base de datos.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


def resolver_area(
    value: Any,
    areas: Optional[Iterable[Dict[str, Any]]] = None,
) -> Optional[str]:
    """Normaliza `area_asignada` a un nombre de área legible."""
    if value is None:
        return None

    texto = str(value).strip()
    if not texto:
        return None
    if texto.lower() == "todas":
        return "Todas"

    catalogo = list(areas or [])
    if texto.isdigit():
        for area in catalogo:
            if str(area.get("id_area")) == texto:
                return str(area.get("nombre_area") or texto)
        return texto

    for area in catalogo:
        nombre = str(area.get("nombre_area") or "").strip()
        if nombre and nombre.lower() == texto.lower():
            return nombre
    return texto


def area_visible(value: Any) -> str:
    """Devuelve un área apta para mostrar en la interfaz."""
    texto = resolver_area(value)
    if not texto or texto.lower() == "todas":
        return ""
    if texto.isdigit():
        return ""
    return texto


def resolver_area_id(
    value: Any,
    areas: Optional[Iterable[Dict[str, Any]]] = None,
) -> Optional[int]:
    """Convierte un nombre o id de área al `id_area` del catálogo.

    Devuelve None para 'Todas', valores vacíos o áreas que no existan en el
    catálogo. No inventa ids ni crea registros.
    """
    if value is None:
        return None

    texto = str(value).strip()
    if not texto or texto.lower() == "todas":
        return None

    catalogo = list(areas or [])
    if texto.isdigit():
        for area in catalogo:
            if str(area.get("id_area")) == texto:
                try:
                    return int(area.get("id_area"))
                except (TypeError, ValueError):
                    return None
        return None

    for area in catalogo:
        nombre = str(area.get("nombre_area") or "").strip()
        if nombre and nombre.lower() == texto.lower():
            try:
                return int(area.get("id_area"))
            except (TypeError, ValueError):
                return None
    return None
