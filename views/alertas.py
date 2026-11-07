"""Pantalla de alertas de stock.

Muestra sin stock, críticos, bajos y los productos recuperados hoy según la
definición D4-A. Todo se calcula desde el inventario visible y el historial.
"""
from __future__ import annotations

from html import escape
from typing import Any, Dict, List

import streamlit as st

from core.exceptions import AuthorizationError
from data.alertas import resumen_alertas
from data.errors import ErrorDatos
from data.permisos import ADMINISTRADOR
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import area_visible, fmt_cantidad, fmt_fecha_hora, fmt_fecha_larga
from ui.layout import metric_grid, page_header, status_badge


def _tabla_alertas(filas: List[Dict[str, Any]], con_recuperacion: bool = False) -> str:
    cuerpo = []
    for fila in filas:
        unidad = str(fila.get("unidad") or "")
        unidad_texto = f" {unidad}" if unidad else ""
        if con_recuperacion:
            detalle = (
                f'<td class="is-date">'
                f'{escape(fmt_fecha_hora(fila.get("recuperado_a")))}</td>'
                f'<td class="is-num">{escape(fmt_cantidad(fila.get("stock_despues")))}'
                f"{escape(unidad_texto)}</td>"
                f"<td>{escape(str(fila.get('area') or 'Sin área'))}</td>"
            )
        else:
            detalle = ""

        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("producto") or "Sin nombre"))}</span></td>'
            f"<td>{escape(str(fila.get('categoria') or 'Sin categoría'))}</td>"
            f"<td>{escape(str(fila.get('unidad') or '—'))}</td>"
            f'<td class="is-num"><strong>'
            f'{escape(fmt_cantidad(fila.get("stock_actual")))}{escape(unidad_texto)}'
            "</strong></td>"
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("stock_minimo")))}'
            f"{escape(unidad_texto)}</td>"
            f"{detalle}"
            f"<td>{status_badge(fila.get('estado'))}</td>"
            "</tr>"
        )

    if con_recuperacion:
        cabecera = (
            "<th>Producto</th><th>Categoría</th><th>Unidad</th>"
            "<th class='is-num'>Stock actual</th>"
            "<th class='is-num'>Mínimo</th>"
            "<th>Recuperado a</th>"
            "<th class='is-num'>Stock al recuperar</th>"
            "<th>Área de la entrada</th><th>Estado actual</th>"
        )
    else:
        cabecera = (
            "<th>Producto</th><th>Categoría</th><th>Unidad</th>"
            "<th class='is-num'>Stock actual</th>"
            "<th class='is-num'>Mínimo</th><th>Estado</th>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        f"<thead><tr>{cabecera}</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _seccion(
    filas: List[Dict[str, Any]],
    *,
    vacio: str,
    con_recuperacion: bool = False,
) -> None:
    if not filas:
        mostrar_vacio(vacio)
        return
    st.markdown(
        f'<div class="ink-table-meta"><span>{len(filas)} producto(s)</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_tabla_alertas(filas, con_recuperacion), unsafe_allow_html=True)


def render_alertas() -> None:
    """Renderiza las alertas de stock del alcance del usuario."""
    user = st.session_state.get("user") or {}
    es_admin = user.get("rol") == ADMINISTRADOR
    area = area_visible(user.get("area_asignada"))

    if es_admin:
        page_header(
            "Alertas de stock",
            "Productos que requieren atención en todas las áreas.",
        )
        alcance = "Vista global · todas las áreas"
        sin_datos = (
            "Aún no hay productos registrados. Cuando agregues productos, "
            "aquí verás los que estén sin stock, críticos o bajos."
        )
    else:
        subtitulo = (
            f"Productos que requieren atención en tu área · {area}"
            if area
            else "Productos que requieren atención en tu área"
        )
        page_header("Alertas de stock", subtitulo)
        alcance = f"Tu área · {area}" if area else "Área no asignada"
        sin_datos = (
            "Aún no hay movimientos en tu área. Cuando se registren entradas, "
            "aquí verás los productos sin stock, críticos o bajos."
        )

    st.markdown(
        f'<div class="ink-scope">{escape(alcance)}</div>',
        unsafe_allow_html=True,
    )

    if not es_admin and not area:
        mostrar_error(
            AuthorizationError(
                "Tu cuenta no tiene un área válida asignada. Contacta al administrador."
            )
        )
        return

    try:
        with cargando("Calculando alertas de stock…"):
            resumen = resumen_alertas(usuario=user)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron calcular las alertas.")
        boton_reintentar("alertas")
        return

    conteos = resumen["conteos"]
    metric_grid(
        [
            {
                "label": "Sin stock",
                "value": fmt_cantidad(conteos["sin_stock"]),
                "hint": "Sin existencias registradas.",
                "tone": "muted",
            },
            {
                "label": "Críticos",
                "value": fmt_cantidad(conteos["criticos"]),
                "hint": "Bajo el 70% del mínimo.",
                "tone": "red",
            },
            {
                "label": "Bajos",
                "value": fmt_cantidad(conteos["bajos"]),
                "hint": "Entre 70% y menos del mínimo.",
                "tone": "amber",
            },
            {
                "label": "Recuperados hoy",
                "value": fmt_cantidad(conteos["recuperados"]),
                "hint": "Entradas de hoy que dejaron el producto sobre el mínimo.",
                "tone": "green",
            },
        ]
    )

    st.markdown(
        '<div class="ink-data-note">'
        f"Alertas calculadas al {escape(fmt_fecha_larga(resumen.get('fecha')))}. "
        "“Recuperados hoy” cuenta las entradas del día que dejaron un producto "
        "en o sobre su mínimo, partiendo de una situación bajo el mínimo. "
        "Es un cálculo del día y no un estado almacenado."
        "</div>",
        unsafe_allow_html=True,
    )

    tab_sin, tab_criticos, tab_bajos, tab_recuperados = st.tabs(
        [
            f"Sin stock ({conteos['sin_stock']})",
            f"Críticos ({conteos['criticos']})",
            f"Bajos ({conteos['bajos']})",
            f"Recuperados hoy ({conteos['recuperados']})",
        ]
    )

    with tab_sin:
        _seccion(
            resumen["sin_stock"],
            vacio=(
                sin_datos
                if resumen["total_productos"] == 0
                else "No hay productos sin stock en este momento."
            ),
        )
    with tab_criticos:
        _seccion(
            resumen["criticos"],
            vacio=(
                sin_datos
                if resumen["total_productos"] == 0
                else "No hay productos en estado crítico. Todos tienen al menos "
                "el 70% de su mínimo."
            ),
        )
    with tab_bajos:
        _seccion(
            resumen["bajos"],
            vacio=(
                sin_datos
                if resumen["total_productos"] == 0
                else "No hay productos en stock bajo. Todos están en o sobre su mínimo."
            ),
        )
    with tab_recuperados:
        _seccion(
            resumen["recuperados"],
            vacio=(
                sin_datos
                if resumen["total_productos"] == 0
                else "Hoy no se han registrado entradas que recuperen un producto "
                "desde bajo su mínimo."
            ),
            con_recuperacion=True,
        )
