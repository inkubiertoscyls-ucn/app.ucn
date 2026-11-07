"""Pantalla de inventario de INKubiertos.

Lista los productos visibles para el usuario con su stock calculado desde los
movimientos, filtros por categoría y estado, y buscador. El área de un operario
se aplica en la capa de datos antes de cualquier filtro de la interfaz.
"""
from __future__ import annotations

from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.inventario import filtrar_inventario, inventario_visible
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import area_visible, fmt_cantidad
from ui.layout import page_header, status_badge

ADMINISTRADOR = "Administrador"
ESTADOS = ["Todos", "Disponible", "Bajo", "Crítico", "Sin stock"]
CLASES_FILA = {"Bajo": "bajo", "Crítico": "critico", "Sin stock": "sin-stock"}


def _cantidad(valor: Optional[float]) -> str:
    return "—" if valor is None else fmt_cantidad(valor)


def _ajuste(valor: Optional[float]) -> str:
    """Muestra el ajuste neto con signo explícito."""
    if valor is None:
        return "—"
    numero = float(valor)
    if numero > 0:
        return f"+{fmt_cantidad(numero)}"
    if numero < 0:
        return f"−{fmt_cantidad(abs(numero))}"
    return "0"


def _tabla_inventario(filas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in filas:
        clase = CLASES_FILA.get(str(fila.get("estado") or ""))
        atributo = f' class="ink-row--{clase}"' if clase else ""
        cuerpo.append(
            f"<tr{atributo}>"
            f'<td><span class="ink-product-name">{escape(str(fila.get("nombre") or "—"))}</span></td>'
            f"<td>{escape(str(fila.get('categoria') or 'Sin categoría'))}</td>"
            f"<td>{escape(str(fila.get('unidad') or '—'))}</td>"
            f'<td class="is-num"><strong>{escape(fmt_cantidad(fila.get("stock_actual")))}</strong></td>'
            f'<td class="is-num ink-delta is-pos">{escape(fmt_cantidad(fila.get("entradas")))}</td>'
            f'<td class="is-num ink-delta is-neg">{escape(fmt_cantidad(fila.get("salidas")))}</td>'
            f'<td class="is-num ink-delta is-neg">{escape(fmt_cantidad(fila.get("mermas")))}</td>'
            f'<td class="is-num">{escape(_ajuste(fila.get("ajustes")))}</td>'
            f'<td class="is-num">{escape(_cantidad(fila.get("stock_minimo")))}</td>'
            f'<td class="is-num">{escape(_cantidad(fila.get("stock_maximo")))}</td>'
            f"<td>{status_badge(fila.get('estado'))}</td>"
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Producto</th><th>Categoría</th><th>Unidad</th>"
        "<th class='is-num'>Stock actual</th>"
        "<th class='is-num'>Entradas</th><th class='is-num'>Salidas</th>"
        "<th class='is-num'>Mermas</th><th class='is-num'>Ajustes</th>"
        "<th class='is-num'>Mínimo</th><th class='is-num'>Máximo</th>"
        "<th>Estado</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _categorias(filas: List[Dict[str, Any]]) -> List[str]:
    return sorted(
        {str(fila.get("categoria") or "Sin categoría") for fila in filas},
        key=lambda valor: (valor.casefold(), valor),
    )


def render_inventario() -> None:
    """Renderiza el inventario global o el del área del operario."""
    user = st.session_state.get("user") or {}
    es_admin = user.get("rol") == ADMINISTRADOR
    area = area_visible(user.get("area_asignada"))

    if es_admin:
        page_header("Inventario", "Existencias por producto en todas las áreas")
        alcance = "Inventario global · todas las áreas"
    else:
        subtitulo = f"Existencias de tu área · {area}" if area else "Existencias de tu área"
        page_header("Inventario", subtitulo)
        alcance = f"Tu área · {area}" if area else "Área no asignada"

    st.markdown(
        f'<div class="ink-scope">{escape(alcance)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "El stock se calcula a partir de todos los movimientos registrados "
        "(sin separar por usuario) y no se almacena como un total aparte. "
        "Entradas y ajustes positivos suman; salidas, mermas y ajustes "
        "negativos restan. «Ajustes» muestra el neto con signo."
    )

    try:
        with cargando("Cargando inventario…"):
            filas = inventario_visible(usuario=user)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo cargar el inventario.")
        boton_reintentar("inventario")
        return

    if not filas:
        if es_admin:
            mostrar_vacio(
                "Aún no hay productos registrados. Cuando agregues productos en "
                "Administración, aparecerán aquí con su categoría, unidad, stock, "
                "mínimos y estado."
            )
        else:
            mostrar_vacio(
                f"Aún no hay movimientos registrados en tu área ({area}). Cuando "
                "se registren entradas o salidas, verás aquí los productos y su "
                "stock disponible."
            )
        return

    col_buscar, col_categoria, col_estado = st.columns(
        [2.2, 1.2, 1.2], gap="medium"
    )
    with col_buscar:
        texto = st.text_input(
            "Buscar producto",
            placeholder="Nombre o categoría",
            key="inv_buscar",
        )
    with col_categoria:
        categoria = st.selectbox(
            "Categoría",
            ["Todas"] + _categorias(filas),
            key="inv_categoria",
        )
    with col_estado:
        estado = st.selectbox("Estado", ESTADOS, key="inv_estado")

    filtradas = filtrar_inventario(
        filas,
        texto=texto,
        categoria=categoria,
        estado=estado,
    )

    detalle_stock = (
        "Stock global sumando todas las áreas."
        if es_admin
        else f"Stock de tu área ({area})."
    )
    st.markdown(
        '<div class="ink-table-meta">'
        f"<span>{len(filtradas)} de {len(filas)} productos</span>"
        f"<span>{escape(detalle_stock)}</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not filtradas:
        mostrar_vacio(
            "No hay productos que coincidan con la búsqueda o los filtros "
            "seleccionados. Prueba con otro término o restablece los filtros."
        )
        if st.button("Limpiar filtros", key="inv_limpiar", type="secondary"):
            for clave in ("inv_buscar", "inv_categoria", "inv_estado"):
                st.session_state.pop(clave, None)
            st.rerun()
        return

    st.markdown(_tabla_inventario(filtradas), unsafe_allow_html=True)
