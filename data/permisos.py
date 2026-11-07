"""Guards de permisos para las lecturas de datos.

Se aplican en la capa de datos, no solo en las vistas, para que ninguna
pantalla pueda consultar información de administración por error.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from core.areas import area_visible
from core.exceptions import AuthorizationError

ADMINISTRADOR = "Administrador"
OPERARIO = "Operario"


def usuario_sesion() -> Optional[Dict[str, Any]]:
    """Devuelve el usuario guardado en la sesión de Streamlit, si existe."""
    try:
        usuario = st.session_state.get("user")
    except Exception:
        return None
    return usuario if isinstance(usuario, dict) else None


def exigir_sesion(usuario: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Exige una sesión válida y una cuenta activa."""
    actual = usuario if usuario is not None else usuario_sesion()
    if not actual:
        raise AuthorizationError("Debes iniciar sesión para consultar esta información.")
    if actual.get("activo") is False:
        raise AuthorizationError("Tu cuenta está inactiva. Contacta al administrador.")
    return actual


def es_admin(usuario: Optional[Dict[str, Any]] = None) -> bool:
    """Indica si el usuario tiene rol Administrador."""
    actual = usuario if usuario is not None else usuario_sesion()
    return bool(actual and actual.get("rol") == ADMINISTRADOR)


def exigir_admin(usuario: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Exige rol Administrador para lecturas de administración."""
    actual = exigir_sesion(usuario)
    if actual.get("rol") != ADMINISTRADOR:
        raise AuthorizationError("Esta sección es exclusiva para administradores.")
    return actual


def area_operario(usuario: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Área fija de un operario; None para un administrador.

    Un operario sin área válida no puede consultar datos globales.
    """
    actual = exigir_sesion(usuario)
    if actual.get("rol") == ADMINISTRADOR:
        return None

    area = area_visible(actual.get("area_asignada"))
    if not area:
        raise AuthorizationError(
            "Tu cuenta no tiene un área válida asignada. Contacta al administrador."
        )
    return area
