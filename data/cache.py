"""Caché de lecturas para Streamlit.

Evita repetir consultas en cada rerun. La caché se puede desactivar con la
variable de entorno INK_DISABLE_CACHE=1 (usada por las pruebas).
"""
from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, List

import streamlit as st

_CACHES: List[Any] = []


def cache_habilitada() -> bool:
    """Indica si la caché está activa en este proceso."""
    valor = os.getenv("INK_DISABLE_CACHE", "").strip().lower()
    return valor not in {"1", "true", "yes", "on"}


def cache_datos(ttl: int = 60) -> Callable:
    """Envuelve una lectura con `st.cache_data` y un TTL en segundos."""

    def decorador(func: Callable) -> Callable:
        cacheada = st.cache_data(ttl=ttl, show_spinner=False)(func)

        @wraps(func)
        def envoltura(*args: Any, **kwargs: Any) -> Any:
            if not cache_habilitada():
                return func(*args, **kwargs)
            return cacheada(*args, **kwargs)

        envoltura.clear = cacheada.clear  # type: ignore[attr-defined]
        envoltura.__wrapped__ = func  # type: ignore[attr-defined]
        _CACHES.append(envoltura)
        return envoltura

    return decorador


def limpiar_cache() -> None:
    """Invalida todas las lecturas cacheadas.

    Debe llamarse después de una escritura (movimiento, alta de producto,
    activación de usuario) y al cerrar sesión.
    """
    for cache in _CACHES:
        try:
            cache.clear()
        except Exception:
            continue
