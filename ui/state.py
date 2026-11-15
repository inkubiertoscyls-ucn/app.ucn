"""Estado de sesión y navegación del frontend."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import streamlit as st

logger = logging.getLogger(__name__)

DEFAULT_STATE = {
    "logged_in": False,
    "user": None,
    "page": "inicio",
    "auth_view": "login",
    "flash": None,
    "ultima_actividad": None,
    "ultima_revalidacion": None,
}

# Cada cuánto se vuelve a leer la cuenta en la base de datos para reflejar
# desactivaciones o cambios de rol hechos por un administrador.
REVALIDAR_CADA_SEGUNDOS = 60


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
    """Cierra la sesión y vuelve al login.

    No se limpia la caché de datos: `st.cache_data` es compartida por todos
    los usuarios conectados y las lecturas ya validan permisos por sesión.
    """
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.page = "inicio"
    st.session_state.auth_view = "login"
    st.session_state.flash = None
    st.session_state.ultima_actividad = None
    st.session_state.ultima_revalidacion = None


def _minutos_inactividad() -> int:
    """Minutos de inactividad permitidos (SESSION_TIMEOUT_MINUTES, por defecto 60)."""
    from config.settings import get_settings

    try:
        minutos = int(get_settings(use_streamlit=True).session_timeout_minutes)
    except Exception:
        minutos = 60
    return minutos if minutos > 0 else 60


def _revalidar_usuario(user: Dict[str, Any]) -> Optional[str]:
    """Relee la cuenta en BD. Devuelve un motivo de cierre o None si sigue válida."""
    from repositories.usuarios import UsuariosRepository

    try:
        actual = UsuariosRepository().get_by_rut(str(user.get("rut_usuario") or ""))
    except Exception as exc:
        # Un corte de red no debe expulsar al usuario; se reintenta luego.
        logger.warning("No se pudo revalidar la sesión: %s", type(exc).__name__)
        return None

    if not actual:
        return "Tu cuenta ya no existe. Contacta al administrador."
    if not actual.get("activo", False):
        return "Tu cuenta fue desactivada. Contacta al administrador."

    for campo in ("nombre_usuario", "rol", "area_asignada", "activo"):
        user[campo] = actual.get(campo)
    return None


def verificar_sesion() -> bool:
    """Aplica el cierre por inactividad y la revalidación periódica.

    Devuelve False si la sesión se cerró (la vista debe mostrar el login).
    """
    user = current_user()
    if not st.session_state.get("logged_in") or not user:
        return False

    ahora = time.time()
    ultima = st.session_state.get("ultima_actividad") or ahora
    if ahora - ultima > _minutos_inactividad() * 60:
        logout()
        flash("warning", "Tu sesión se cerró por inactividad. Ingresa nuevamente.")
        return False
    st.session_state.ultima_actividad = ahora

    revisada = st.session_state.get("ultima_revalidacion") or 0
    if ahora - revisada >= REVALIDAR_CADA_SEGUNDOS:
        motivo = _revalidar_usuario(user)
        st.session_state.ultima_revalidacion = ahora
        if motivo:
            logout()
            flash("error", motivo)
            return False
    return True


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
