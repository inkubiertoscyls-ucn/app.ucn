"""Pantalla de Rentabilidad de INKubiertos.

Muestra las ventas reales importadas desde FUDO y calcula costo, utilidad y
margen solo cuando existe producto vinculado, cantidad informada y costo base
válido. Las ventas sin costo se informan aparte y nunca se presentan como
utilidad cero. No se calcula rentabilidad por área ni se inventan eventos.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from core.exceptions import AuthorizationError
from data.catalogos import listar_eventos
from data.errors import ErrorDatos
from data.permisos import ADMINISTRADOR
from data.ventas import resumen_rentabilidad
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_cantidad, fmt_clp, fmt_fecha_larga, fmt_pct
from ui.layout import metric_grid, page_header, status_badge
from ui.state import go


def _clp(valor: Any) -> str:
    return fmt_clp(valor) if valor is not None else "—"


def _pct(valor: Any) -> str:
    return fmt_pct(valor, 1) if valor is not None else "—"


def _tabla_agrupada(
    filas: List[Dict[str, Any]],
    *,
    etiqueta: str,
) -> str:
    cuerpo = []
    for fila in filas:
        nombre = str(fila.get(etiqueta) or "—")
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">{escape(nombre)}</span>'
            + (
                f'<div class="ink-muted">{escape(str(fila.get("categoria") or ""))}</div>'
                if etiqueta == "Producto" and fila.get("categoria")
                else ""
            )
            + "</td>"
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("registros")))}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("cantidad")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("ventas")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("costo")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("utilidad")))}</td>'
            f'<td class="is-num">{escape(_pct(fila.get("margen")))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        f"<thead><tr><th>{escape(etiqueta)}</th>"
        "<th class='is-num'>Registros</th>"
        "<th class='is-num'>Cantidad</th>"
        "<th class='is-num'>Ventas</th>"
        "<th class='is-num'>Costo estimado</th>"
        "<th class='is-num'>Utilidad estimada</th>"
        "<th class='is-num'>Margen estimado</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_sin_costo(filas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in filas:
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("producto") or "—"))}</span></td>'
            f'<td>{escape(str(fila.get("categoria") or "Sin categoría"))}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("registros")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("monto")))}</td>'
            f'<td>{status_badge("Sin costo", "amber")}</td>'
            f'<td class="ink-muted">{escape(str(fila.get("motivo") or "—"))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Producto</th><th>Categoría</th>"
        "<th class='is-num'>Registros</th>"
        "<th class='is-num'>Monto informado</th>"
        "<th>Estado</th><th>Motivo</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_eventos(filas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in filas:
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("evento") or "Sin evento"))}</span></td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("registros")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("ventas")))}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("identificadas")))}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("pendientes")))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Evento</th>"
        "<th class='is-num'>Ventas</th>"
        "<th class='is-num'>Monto</th>"
        "<th class='is-num'>Identificadas</th>"
        "<th class='is-num'>Pendientes</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _graficos(resumen: Dict[str, Any]) -> None:
    categorias = resumen.get("por_categoria") or []
    productos = resumen.get("por_producto") or []

    if not categorias and not productos:
        mostrar_vacio(
            "Aún no hay ventas identificadas con costo base válido para "
            "graficar. Cuando vincules productos y tengan costo, aparecerán aquí."
        )
        return

    col_categoria, col_producto = st.columns(2)
    with col_categoria:
        st.markdown("**Utilidad estimada por categoría**")
        if categorias:
            datos = pd.DataFrame(
                [
                    {
                        "Categoría": str(fila.get("categoria") or "Sin categoría"),
                        "Utilidad estimada": float(fila.get("utilidad") or 0),
                    }
                    for fila in categorias
                ]
            )
            st.bar_chart(
                datos.set_index("Categoría"),
                height=300,
                use_container_width=True,
            )
        else:
            st.caption("Sin ventas con costo para agrupar por categoría.")

    with col_producto:
        st.markdown("**Ventas por producto**")
        if productos:
            top = sorted(
                productos,
                key=lambda fila: float(fila.get("ventas") or 0),
                reverse=True,
            )[:10]
            datos = pd.DataFrame(
                [
                    {
                        "Producto": str(fila.get("producto") or "Sin nombre"),
                        "Ventas": float(fila.get("ventas") or 0),
                    }
                    for fila in top
                ]
            )
            st.bar_chart(
                datos.set_index("Producto"),
                height=300,
                use_container_width=True,
            )
            st.caption("Se muestran los 10 productos con mayores ventas estimadas.")
        else:
            st.caption("Sin ventas con costo para agrupar por producto.")


def render_rentabilidad() -> None:
    """Renderiza el resumen de rentabilidad estimada."""
    user = st.session_state.get("user") or {}
    if user.get("rol") != ADMINISTRADOR:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

    page_header(
        "Rentabilidad",
        "Ventas reales de FUDO y estimaciones de costo, utilidad y margen.",
    )
    st.markdown(
        '<div class="ink-scope">Administración · estimaciones sobre ventas FUDO</div>',
        unsafe_allow_html=True,
    )

    try:
        eventos = listar_eventos(incluir_inactivos=True)
    except ErrorDatos as exc:
        mostrar_error(exc, prefijo="No se pudo cargar el catálogo de eventos.")
        eventos = []

    hoy = date.today()
    col_desde, col_hasta, col_todo = st.columns([1, 1, 1])
    with col_desde:
        desde = st.date_input(
            "Desde",
            value=hoy - timedelta(days=90),
            key="rent_desde",
        )
    with col_hasta:
        hasta = st.date_input("Hasta", value=hoy, key="rent_hasta")
    with col_todo:
        st.write("")
        todo = st.checkbox(
            "Todo el período",
            key="rent_todo",
            help="Incluye todas las ventas importadas, sin límite de fechas.",
        )

    evento_filtro: Optional[int] = None
    if eventos:
        opciones = [None] + eventos
        evento = st.selectbox(
            "Evento registrado",
            opciones,
            format_func=lambda item: (
                "Todos los eventos"
                if item is None
                else str(item.get("nombre_evento") or "Sin nombre")
            ),
            key="rent_evento",
            help=(
                "Solo se filtran ventas que ya tienen un evento almacenado. "
                "El filtro no crea relaciones entre ventas y eventos."
            ),
        )
        if evento is not None:
            try:
                evento_filtro = int(evento.get("id_evento"))
            except (TypeError, ValueError):
                evento_filtro = None
    else:
        st.caption(
            "No hay eventos registrados en el catálogo. Las ventas se muestran "
            "sin filtro por evento."
        )

    if desde > hasta and not todo:
        st.warning("La fecha desde no puede ser posterior a la fecha hasta.")
        return

    try:
        with cargando("Calculando rentabilidad estimada…"):
            resumen = resumen_rentabilidad(
                desde=None if todo else desde,
                hasta=None if todo else hasta,
                id_evento=evento_filtro,
                usuario=user,
            )
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo calcular la rentabilidad.")
        boton_reintentar("rentabilidad")
        return

    registros_sin_total = int(resumen.get("registros_sin_total") or 0)
    registros_sin_cantidad = int(resumen.get("registros_sin_cantidad") or 0)
    pendientes = int(resumen.get("ventas_pendientes") or 0)
    sin_costo = int(resumen.get("ventas_identificadas_sin_costo") or 0)

    hint_ventas = "Todas las ventas importadas, con o sin producto vinculado."
    if registros_sin_total:
        hint_ventas += f" {registros_sin_total} registro(s) sin total informado."

    hint_cantidad = "Cantidad informada en el archivo de FUDO."
    if registros_sin_cantidad:
        hint_cantidad += f" {registros_sin_cantidad} registro(s) sin cantidad."

    metric_grid(
        [
            {
                "label": "Ventas reales",
                "value": _clp(resumen.get("ventas_totales")),
                "hint": hint_ventas,
                "tone": "wine",
            },
            {
                "label": "Cantidad vendida",
                "value": (
                    fmt_cantidad(resumen.get("cantidad_total"))
                    if resumen.get("cantidad_total") is not None
                    else "—"
                ),
                "hint": hint_cantidad,
                "tone": "default",
            },
            {
                "label": "Ventas identificadas",
                "value": fmt_cantidad(resumen.get("ventas_identificadas")),
                "hint": "Con producto vinculado, tengan o no costo válido.",
                "tone": "green",
            },
            {
                "label": "Pendientes de vincular",
                "value": fmt_cantidad(pendientes),
                "hint": "Sin producto. No se les asigna utilidad cero.",
                "tone": "amber",
            },
        ]
    )

    metric_grid(
        [
            {
                "label": "Costo estimado",
                "value": _clp(resumen.get("costo_estimado")),
                "hint": "Calculado con el costo_base vigente, no histórico.",
                "tone": "muted",
            },
            {
                "label": "Utilidad bruta estimada",
                "value": _clp(resumen.get("utilidad_estimada")),
                "hint": "Solo ventas con producto, cantidad y costo válidos.",
                "tone": "green",
            },
            {
                "label": "Margen estimado",
                "value": _pct(resumen.get("margen_estimado")),
                "hint": "Sobre las ventas que sí tienen costo estimado.",
                "tone": "default",
            },
        ]
    )

    st.markdown(
        '<div class="ink-data-note">'
        f"Estimación calculada al {escape(fmt_fecha_larga(hoy))}. "
        "Los costos, la utilidad y el margen usan el costo base actual de cada "
        "producto y no representan costos históricos ni utilidad contable. "
        "Las ventas sin producto vinculado, sin cantidad o sin costo válido no "
        "se suman como utilidad cero: se informan por separado."
        + (
            " No se calcula rentabilidad por área porque las ventas de FUDO no "
            "tienen área asociada."
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if pendientes:
        st.info(
            f"{fmt_cantidad(pendientes)} venta(s) están pendientes de vinculación "
            f"por un total informado de {_clp(resumen.get('monto_pendiente'))}. "
            "No se incluyen en el costo ni en la utilidad estimada."
        )
    if sin_costo:
        st.warning(
            f"{fmt_cantidad(sin_costo)} venta(s) identificadas no tienen costo, "
            "cantidad o total suficiente para estimar su utilidad. Se muestran "
            "aparte y no se contabilizan como utilidad cero."
        )
    if resumen.get("truncado"):
        st.warning(
            "Se analizaron las primeras 10.000 ventas del período. Acota las "
            "fechas para un cálculo completo."
        )

    if not resumen.get("con_datos"):
        mostrar_vacio(
            "Aún no hay ventas importadas para el período seleccionado. "
            "Carga un archivo desde Ventas de FUDO para comenzar."
        )
        if st.button("Ir a Ventas de FUDO", key="rent_ir_fudo", type="primary"):
            go("fudo")
        return

    st.markdown("---")
    _graficos(resumen)

    categorias = resumen.get("por_categoria") or []
    productos = resumen.get("por_producto") or []
    if categorias or productos:
        with st.expander("Detalle por categoría", expanded=True):
            if categorias:
                st.markdown(
                    _tabla_agrupada(categorias, etiqueta="Categoría"),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Sin categorías con costo válido.")
        with st.expander("Detalle por producto", expanded=False):
            if productos:
                st.markdown(
                    _tabla_agrupada(productos, etiqueta="Producto"),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Sin productos con costo válido.")

    detalle_sin_costo = resumen.get("sin_costo") or []
    if detalle_sin_costo:
        with st.expander(
            f"Ventas identificadas sin costo estimable ({len(detalle_sin_costo)})",
            expanded=True,
        ):
            st.caption(
                "Estas ventas no se incluyen en el costo ni en la utilidad. "
                "No se muestran como utilidad cero."
            )
            st.markdown(
                _tabla_sin_costo(detalle_sin_costo),
                unsafe_allow_html=True,
            )

    eventos_agrupados = resumen.get("eventos") or []
    eventos_con_id = [
        fila for fila in eventos_agrupados if fila.get("id_evento") is not None
    ]
    with st.expander("Ventas por evento registrado", expanded=False):
        if eventos_con_id:
            st.caption(
                "Solo se agrupan ventas que ya tienen un id_evento almacenado. "
                "No se infiere ni se inventa una relación entre ventas y eventos."
            )
            st.markdown(
                _tabla_eventos(eventos_agrupados),
                unsafe_allow_html=True,
            )
        else:
            st.info(
                "Las ventas analizadas no tienen evento registrado. No se "
                "atribuyen ventas a eventos."
            )
