"""Estado de sesión y navegación del frontend."""
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

DEFAULT_STATE = {
    "logged_in": False,
    "user": None,
    "page": "inicio",
    "auth_view": "login",
    "flash": None,
}


def init_state() -> None:
    """Inicializa las claves de sesión sin sobrescribir valores existentes."""
    for key, value in DEFAULT_STATE.items():
        st.session_state.setdefault(key, value)


def current_user() -> Optional[Dict[str, Any]]:
    user = st.session_state.get("user")
    return user if isinstance(user, dict) else None


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("rol") == "Administrador")


def go(page: str, **kwargs: Any) -> None:
    """Navega a una pantalla y solicita un rerun."""
    st.session_state.page = page
    for key, value in kwargs.items():
        st.session_state[key] = value
    st.rerun()


def logout() -> None:
    """Cierra la sesión y vuelve al login."""
    from data.cache import limpiar_cache

    limpiar_cache()
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.page = "inicio"
    st.session_state.auth_view = "login"
    st.session_state.flash = None


def flash(kind: str, message: str) -> None:
    """Guarda un mensaje para mostrarlo después del rerun."""
    st.session_state.flash = {"kind": kind, "message": message}


def render_flash() -> None:
    """Muestra y consume el mensaje pendiente."""
    pending = st.session_state.get("flash")
    if not pending:
        return

    kind = pending.get("kind", "info")
    message = str(pending.get("message", ""))
    st.session_state.flash = None

    if kind == "success":
        st.success(message)
    elif kind == "warning":
        st.warning(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def require_role(role: str) -> None:
    """Detiene la vista si el usuario no tiene el rol requerido."""
    user = current_user()
    if not user:
        st.stop()
    if user.get("rol") != role:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()


def require_login() -> None:
    """Detiene la vista si no hay una sesión iniciada."""
    if not st.session_state.get("logged_in") or not current_user():
        st.session_state.auth_view = "login"
        st.stop()
