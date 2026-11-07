"""Componentes visuales reutilizables."""
from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable, Optional

import streamlit as st

from ui.format import area_visible

TONOS_METRICA = {"default", "wine", "green", "amber", "red", "muted"}
TONOS_ESTADO = {
    "Disponible": "green",
    "Bajo": "amber",
    "Crítico": "red",
    "Sin stock": "muted",
    "Entrada": "green",
    "Salida": "red",
    "Merma": "amber",
    "Ajuste positivo": "green",
    "Ajuste negativo": "red",
}


def page_header(title: str, subtitle: Optional[str] = None) -> None:
    """Encabezado estándar de una pantalla."""
    subtitle_html = (
        f'<p class="ink-page-subtitle">{escape(str(subtitle))}</p>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class="ink-page-head">
            <h1 class="ink-page-title">{escape(str(title))}</h1>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def top_bar(user: Optional[Dict[str, Any]] = None) -> None:
    """Barra de contexto con la marca y el usuario de la sesión."""
    if not user:
        return

    nombre = escape(str(user.get("nombre_usuario") or "Usuario"))
    rol = escape(str(user.get("rol") or ""))
    area = escape(area_visible(user.get("area_asignada")))
    area_html = f'<span class="ink-topbar-role">{area}</span>' if area else ""
    rol_html = f'<span class="ink-topbar-role">{rol}</span>' if rol else ""

    st.markdown(
        f"""
        <div class="ink-topbar">
            <div class="ink-topbar-brand">INKubiertos</div>
            <div class="ink-topbar-right">
                <span class="ink-topbar-user">{nombre}</span>
                {rol_html}
                {area_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_grid(
    items: Iterable[Dict[str, Any]],
    columns: Optional[int] = None,
) -> None:
    """Tarjetas de indicadores en una grilla responsive.

    Si no se indica `columns`, el ancho se deriva de la cantidad de
    indicadores recibidos.
    """
    tarjetas = []
    total = 0
    for item in items:
        total += 1
        tono = str(item.get("tone") or "default")
        if tono not in TONOS_METRICA:
            tono = "default"
        etiqueta = escape(str(item.get("label") or ""))
        valor_raw = item.get("value")
        valor = escape("—" if valor_raw is None else str(valor_raw))
        pista = item.get("hint")
        pista_html = (
            f'<div class="ink-metric-hint">{escape(str(pista))}</div>'
            if pista
            else ""
        )
        tarjetas.append(
            f'<div class="ink-metric ink-metric--{tono}">'
            f'<div class="ink-metric-label">{etiqueta}</div>'
            f'<div class="ink-metric-value">{valor}</div>'
            f"{pista_html}"
            "</div>"
        )

    ancho = columns if columns else total
    clase = (
        f" ink-metrics--{ancho}"
        if ancho and 2 <= ancho <= 5 and ancho != 5
        else ""
    )
    st.markdown(
        f'<div class="ink-metrics{clase}">{"".join(tarjetas)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(label: Any, tone: Optional[str] = None) -> str:
    """Devuelve una etiqueta de estado con color semántico."""
    texto = str(label or "—")
    tono = tone or TONOS_ESTADO.get(texto, "muted")
    if tono not in TONOS_METRICA:
        tono = "muted"
    return (
        f'<span class="ink-status ink-status--{tono}">'
        f"{escape(texto)}</span>"
    )


def placeholder(title: str, message: str, badge: str = "Próxima etapa") -> None:
    """Tarjeta informativa para pantallas aún no implementadas."""
    st.markdown(
        f"""
        <div class="ink-placeholder">
            <div class="ink-placeholder-badge">{escape(badge)}</div>
            <div class="ink-placeholder-title">{escape(title)}</div>
            <p class="ink-placeholder-text">{escape(message)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    """Mensaje para listas o tablas sin datos."""
    st.markdown(
        f'<div class="ink-empty-state">{escape(message)}</div>',
        unsafe_allow_html=True,
    )
