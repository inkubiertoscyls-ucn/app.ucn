"""Dashboard de inicio de INKubiertos.

Muestra indicadores reales del inventario visible para el usuario, el valor
estimado y los movimientos recientes. No crea ni modifica datos.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from data.catalogos import listar_areas, listar_tipos_movimiento
from data.errors import ErrorDatos
from data.inventario import resumen_inventario, ultimos_movimientos
from data.productos import listar_productos
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import area_visible, fmt_cantidad, fmt_clp, fmt_fecha_hora
from ui.layout import metric_grid, page_header, status_badge

ADMINISTRADOR = "Administrador"


def _numero(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _id_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _panel_valor(resumen: Dict[str, Any]) -> str:
    total = int(resumen.get("total_productos") or 0)
    valor = resumen.get("valor_estimado")
    con_costo = int(resumen.get("productos_con_costo") or 0)
    valorizados = int(resumen.get("productos_valorizados") or 0)

    if valor is not None:
        valor_html = f'<div class="ink-panel-value">{escape(fmt_clp(valor))}</div>'
        pista = (
            f"Calculado con {valorizados} de {total} productos con costo base "
            "y stock positivo. Los productos sin costo se excluyen."
        )
    else:
        valor_html = (
            '<div class="ink-panel-value ink-panel-value--muted">—</div>'
        )
        if total == 0:
            pista = "Aún no hay productos registrados para valorizar."
        elif con_costo == 0:
            pista = (
                "Ningún producto tiene costo base registrado. El valor aparecerá "
                "cuando existan costos y existencias válidas."
            )
        else:
            pista = (
                "Los productos con costo registrado no tienen existencias "
                "positivas para valorizar."
            )

    return (
        '<div class="ink-panel ink-panel--value">'
        '<div class="ink-panel-label">Valor estimado del inventario</div>'
        f"{valor_html}"
        f'<div class="ink-panel-hint">{escape(pista)}</div>'
        "</div>"
    )


def _panel_actualizacion(ultimo: Optional[Dict[str, Any]]) -> str:
    ahora = datetime.now()
    sello = ahora.strftime("%d/%m/%Y · %H:%M")

    if ultimo:
        fecha_movimiento = fmt_fecha_hora(ultimo.get("fecha_hora_registro"))
        detalle = (
            f"Último movimiento: {fecha_movimiento}"
            if fecha_movimiento != "—"
            else "Último movimiento sin fecha registrada."
        )
    else:
        detalle = "Sin movimientos registrados."

    return (
        '<div class="ink-panel">'
        '<div class="ink-panel-label">Última actualización</div>'
        f'<div class="ink-panel-stamp">{escape(sello)}</div>'
        '<div class="ink-panel-hint">Consulta en vivo a Supabase.</div>'
        f'<div class="ink-panel-hint">{escape(detalle)}</div>'
        "</div>"
    )


def _mapas_movimientos(
    productos: List[Dict[str, Any]],
    areas: List[Dict[str, Any]],
    tipos: List[Dict[str, Any]],
) -> tuple[Dict[int, str], Dict[int, str], Dict[int, Dict[str, Any]]]:
    mapa_productos = {
        id_producto: str(producto.get("nombre_producto") or "Sin nombre")
        for producto in productos
        if (id_producto := _id_int(producto.get("id_producto"))) is not None
    }
    mapa_areas = {
        id_area: str(area.get("nombre_area") or "Sin área")
        for area in areas
        if (id_area := _id_int(area.get("id_area"))) is not None
    }
    mapa_tipos = {
        id_tipo: tipo
        for tipo in tipos
        if (id_tipo := _id_int(tipo.get("id_tipo_movimiento"))) is not None
    }
    return mapa_productos, mapa_areas, mapa_tipos


def _tabla_movimientos(
    movimientos: List[Dict[str, Any]],
    mapa_productos: Dict[int, str],
    mapa_areas: Dict[int, str],
    mapa_tipos: Dict[int, Dict[str, Any]],
) -> str:
    filas = []
    for movimiento in movimientos:
        id_producto = _id_int(movimiento.get("id_producto"))
        id_area = _id_int(movimiento.get("id_area"))
        id_tipo = _id_int(movimiento.get("id_tipo_movimiento"))

        producto = mapa_productos.get(id_producto) if id_producto is not None else None
        area = mapa_areas.get(id_area) if id_area is not None else None
        tipo = mapa_tipos.get(id_tipo) if id_tipo is not None else None
        tipo = tipo or {}
        producto = producto or "Producto sin identificar"
        area = area or "Sin área"
        nombre_tipo = str(tipo.get("tipo_movimiento") or "Sin tipo")

        factor = _numero(tipo.get("factor_stock"))
        tono = "green" if factor == 1 else "red" if factor == -1 else "muted"
        cantidad = _numero(movimiento.get("cantidad"))
        if cantidad is None:
            cantidad_texto = "—"
        elif factor == 1:
            cantidad_texto = f"+{fmt_cantidad(abs(cantidad))}"
        elif factor == -1:
            cantidad_texto = f"−{fmt_cantidad(abs(cantidad))}"
        else:
            cantidad_texto = fmt_cantidad(cantidad)

        fecha = fmt_fecha_hora(movimiento.get("fecha_hora_registro"))
        rut = str(movimiento.get("rut_usuario") or "—")

        filas.append(
            "<tr>"
            f'<td class="is-date">{escape(fecha)}</td>'
            f'<td><span class="ink-product-name">{escape(producto)}</span></td>'
            f"<td>{status_badge(nombre_tipo, tono)}</td>"
            f'<td class="is-num">{escape(cantidad_texto)}</td>'
            f"<td>{escape(area)}</td>"
            f'<td class="is-date">{escape(rut)}</td>'
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Fecha</th><th>Producto</th><th>Tipo</th>"
        "<th class='is-num'>Cantidad</th><th>Área</th><th>Usuario</th>"
        "</tr></thead>"
        f'<tbody>{"".join(filas)}</tbody>'
        "</table>"
        "</div>"
    )


def render_inicio() -> None:
    """Renderiza el dashboard según el rol y el área del usuario."""
    user = st.session_state.get("user") or {}
    es_admin = user.get("rol") == ADMINISTRADOR
    area = area_visible(user.get("area_asignada"))

    if es_admin:
        page_header("Inicio", "Panel general de gestión")
        alcance = "Inventario global · todas las áreas"
    else:
        subtitulo = f"Resumen de tu área · {area}" if area else "Resumen de tu área"
        page_header("Inicio", subtitulo)
        alcance = f"Tu área · {area}" if area else "Área no asignada"

    st.markdown(
        f'<div class="ink-scope">{escape(alcance)}</div>',
        unsafe_allow_html=True,
    )

    try:
        with cargando("Cargando resumen del inventario…"):
            resumen = resumen_inventario(usuario=user)
            movimientos = ultimos_movimientos(8, usuario=user)
            if movimientos:
                productos = listar_productos(solo_activos=True)
                areas = listar_areas()
                tipos = listar_tipos_movimiento()
            else:
                productos, areas, tipos = [], [], []
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo cargar el inicio.")
        boton_reintentar("inicio")
        return

    metric_grid(
        [
            {
                "label": "Total de productos" if es_admin else "Productos en tu área",
                "value": fmt_cantidad(resumen.get("total_productos")),
                "hint": "Productos activos con stock visible.",
                "tone": "wine",
            },
            {
                "label": "Disponibles",
                "value": fmt_cantidad(resumen.get("disponibles")),
                "hint": "Stock en o sobre el mínimo.",
                "tone": "green",
            },
            {
                "label": "Stock bajo",
                "value": fmt_cantidad(resumen.get("bajos")),
                "hint": "Entre 70% y menos del mínimo.",
                "tone": "amber",
            },
            {
                "label": "Críticos",
                "value": fmt_cantidad(resumen.get("criticos")),
                "hint": "Bajo el 70% del mínimo.",
                "tone": "red",
            },
            {
                "label": "Sin stock",
                "value": fmt_cantidad(resumen.get("sin_stock")),
                "hint": "Sin existencias registradas.",
                "tone": "muted",
            },
        ]
    )

    col_valor, col_actualizacion = st.columns([2, 1], gap="large")
    with col_valor:
        st.markdown(_panel_valor(resumen), unsafe_allow_html=True)
    with col_actualizacion:
        st.markdown(
            _panel_actualizacion(movimientos[0] if movimientos else None),
            unsafe_allow_html=True,
        )

    if int(resumen.get("total_productos") or 0) == 0:
        if es_admin:
            mostrar_vacio(
                "Aún no hay productos registrados. Cuando agregues productos, "
                "verás aquí el total, los estados de stock y el valor estimado "
                "del inventario."
            )
        else:
            mostrar_vacio(
                f"Aún no hay movimientos registrados en tu área ({area}). "
                "Cuando se registren entradas o salidas, verás aquí el resumen "
                "de existencias de tu área."
            )

    st.markdown("## Movimientos recientes")
    if movimientos:
        st.caption(
            "Últimos movimientos de todas las áreas."
            if es_admin
            else "Últimos movimientos de tu área."
        )
        mapa_productos, mapa_areas, mapa_tipos = _mapas_movimientos(
            productos, areas, tipos
        )
        st.markdown(
            _tabla_movimientos(
                movimientos,
                mapa_productos,
                mapa_areas,
                mapa_tipos,
            ),
            unsafe_allow_html=True,
        )
    else:
        mostrar_vacio(
            "Aún no hay movimientos registrados. Cuando se registren entradas, "
            "salidas o ajustes, aparecerán aquí los últimos movimientos."
        )
