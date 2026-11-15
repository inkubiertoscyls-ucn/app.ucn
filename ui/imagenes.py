"""Rutas de las imágenes decorativas de la interfaz.

Las imágenes se generan desde `imagenes/` con `scripts/generar_imagenes.py`
y se guardan en `static/`, que Streamlit publica en `app/static/` gracias a
`enableStaticServing` (ver `.streamlit/config.toml`). Así el navegador las
descarga una sola vez y las guarda en caché.
"""
from __future__ import annotations

from pathlib import Path

CARPETA_STATIC = Path(__file__).resolve().parent.parent / "static"
URL_STATIC = "app/static"

LOGO_BLANCO = f"{URL_STATIC}/logo_blanco.png"
LOGO_NEGRO = f"{URL_STATIC}/logo_negro.png"
FONDO = f"{URL_STATIC}/fondo.jpg"


def icono_pagina() -> str | None:
    """Ruta local del ícono de la pestaña; None si aún no se generó."""
    ruta = CARPETA_STATIC / "icono.png"
    return str(ruta) if ruta.exists() else None
