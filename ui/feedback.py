"""Estados de carga, error y vacío para las pantallas de datos."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import streamlit as st

from data.errors import (
    CONEXION,
    ESQUEMA,
    INTERNO,
    PERMISOS,
    ErrorDatos,
    como_error,
)
from ui.layout import empty_state


@contextmanager
def cargando(mensaje: str = "Cargando información…") -> Iterator[None]:
    """Muestra un spinner mientras dura la consulta."""
    with st.spinner(mensaje):
        yield


def mostrar_error(exc: BaseException, *, prefijo: Optional[str] = None) -> ErrorDatos:
    """Muestra un error de datos en español, sin detalles técnicos."""
    error = como_error(exc)
    mensaje = f"{prefijo} {error.mensaje}".strip() if prefijo else error.mensaje
    st.error(mensaje)

    if error.tipo == CONEXION:
        st.caption(
            "Revisa tu conexión a internet. Si el problema continúa, "
            "contacta al administrador."
        )
    elif error.tipo == PERMISOS:
        st.caption("Si crees que se trata de un error, contacta al administrador.")
    elif error.tipo == ESQUEMA:
        st.caption("La base de datos no está disponible en este momento.")
    elif error.tipo == INTERNO:
        st.caption(
            "Este es un problema de la aplicación, no de tu conexión a "
            "internet. Contacta al administrador."
        )
    return error


def mostrar_vacio(mensaje: str = "No hay datos para mostrar.") -> None:
    """Estado vacío estándar para listas y tablas."""
    empty_state(mensaje)


def boton_reintentar(clave: str, etiqueta: str = "Reintentar") -> None:
    """Invalida la caché y vuelve a cargar la pantalla actual."""
    if st.button(etiqueta, key=f"reintentar_{clave}", type="secondary"):
        from data.cache import limpiar_cache

        limpiar_cache()
        st.rerun()
