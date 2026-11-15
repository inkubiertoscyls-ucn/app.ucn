"""Pantalla de Rentabilidad de INKubiertos.

Muestra las ventas reales importadas desde FUDO y calcula costo, utilidad y
margen solo cuando existe producto vinculado, cantidad informada y costo base
válido. Las ventas sin costo se informan aparte y nunca se presentan como
utilidad cero. No se calcula rentabilidad por área ni se inventan eventos.

La rentabilidad por artista usa la fecha de presentación de cada evento
(`fecha_evento`) y las ventas de FUDO de ese mismo día, comparadas con el
promedio de los días sin evento.
"""
from __future__ import annotations

from datetime import timedelta
from html import escape
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from core.tiempo import hoy_chile
from core.exceptions import AuthorizationError
from data.catalogos import listar_eventos
from data.errors import ErrorDatos
from data.permisos import ADMINISTRADOR
from data.ventas import resumen_rentabilidad
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_cantidad, fmt_clp, fmt_fecha, fmt_fecha_larga, fmt_pct
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
                width="stretch",
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
                width="stretch",
            )
            st.caption("Se muestran los 10 productos con mayores ventas estimadas.")
        else:
            st.caption("Sin ventas con costo para agrupar por producto.")


ESTADOS_VISITA = {
    "calculado": ("Calculado", "green"),
    "sin_ventas": ("Sin ventas importadas", "amber"),
    "programado": ("Programado", "muted"),
}


def _clp_signo(valor: Any) -> str:
    """Monto con color: verde si gana, rojo si pierde."""
    if valor is None:
        return "—"
    clase = "is-pos" if valor > 0 else "is-neg" if valor < 0 else ""
    signo = "+" if valor > 0 else ""
    return f'<span class="ink-delta {clase}">{escape(signo + fmt_clp(valor))}</span>'


def _tabla_visitas(visitas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in visitas:
        etiqueta, tono = ESTADOS_VISITA.get(fila.get("estado"), ("—", "muted"))
        notas = []
        if (fila.get("comparte_dia") or 1) > 1:
            notas.append(f"Día compartido con {fila['comparte_dia'] - 1} evento(s) más")
        if fila.get("parcial"):
            notas.append(
                f"{_clp(fila.get('monto_sin_costo'))} sin costo"
            )
        nota_html = (
            f'<div class="ink-muted">{escape(" · ".join(notas))}</div>' if notas else ""
        )
        cuerpo.append(
            "<tr>"
            f'<td class="is-date">{escape(fmt_fecha(fila.get("fecha")))}</td>'
            f'<td><span class="ink-product-name">{escape(str(fila.get("artista")))}</span>'
            f'<div class="ink-muted">{escape(str(fila.get("evento")))}</div>'
            f"{status_badge(etiqueta, tono)}{nota_html}</td>"
            f'<td class="is-num">{escape(_clp(fila.get("ventas")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("utilidad_bruta")))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("costo_artista")))}</td>'
            f'<td class="is-num">{_clp_signo(fila.get("ganancia_dia"))}</td>'
            f'<td class="is-num">{_clp_signo(fila.get("aporte_ventas"))}</td>'
            f'<td class="is-num">{_clp_signo(fila.get("ganancia_vs_normal"))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Fecha</th><th>Artista · evento</th>"
        "<th class='is-num'>Ventas</th>"
        "<th class='is-num'>Utilidad</th>"
        "<th class='is-num'>Pago artista</th>"
        "<th class='is-num'>Ganancia</th>"
        "<th class='is-num'>Ventas vs. normal</th>"
        "<th class='is-num'>Ganancia vs. normal</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_por_artista(artistas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in artistas:
        visitas = int(fila.get("visitas") or 0)
        calculadas = int(fila.get("visitas_calculadas") or 0)
        detalle_visitas = (
            f"{calculadas} de {visitas}" if calculadas != visitas else str(visitas)
        )
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">{escape(str(fila.get("artista")))}</span>'
            + (
                f'<div class="ink-muted">{escape(fmt_fecha(fila.get("ultima_fecha")))}</div>'
                if fila.get("ultima_fecha")
                else ""
            )
            + "</td>"
            + "<td>"
            + (
                status_badge("Parcial", "amber")
                if fila.get("parcial")
                else status_badge("Completa", "green")
                if fila.get("visitas_calculadas")
                else status_badge("Sin datos", "muted")
            )
            + "</td>"
            f'<td class="is-num">{escape(detalle_visitas)}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("ventas")))}</td>'
            f'<td class="is-num">{_clp_signo(fila.get("aporte_ventas"))}</td>'
            f'<td class="is-num">{escape(_clp(fila.get("costo_artista")))}</td>'
            f'<td class="is-num">{_clp_signo(fila.get("ganancia_dia"))}</td>'
            f'<td class="is-num">{_clp_signo(fila.get("ganancia_vs_normal"))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Artista</th>"
        "<th title='Parcial: algunas ventas del día no tienen costo estimable'>Datos</th>"
        "<th class='is-num'>Visitas</th>"
        "<th class='is-num'>Ventas</th>"
        "<th class='is-num'>Ventas vs. normal</th>"
        "<th class='is-num'>Pago artista</th>"
        "<th class='is-num'>Ganancia</th>"
        "<th class='is-num'>Ganancia vs. normal</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _seccion_artistas(datos: Optional[Dict[str, Any]], filtro_evento: bool) -> None:
    """Rentabilidad de cada visita de artista según las ventas de ese día."""
    st.markdown("### Rentabilidad por artista")

    if filtro_evento or datos is None:
        st.info(
            "La rentabilidad por artista se calcula con todas las ventas del "
            "período. Selecciona «Todos los eventos» para verla."
        )
        return

    if not datos.get("columna_disponible"):
        st.warning(
            "Falta la fecha de presentación en los eventos. Ejecuta la migración "
            "`db/migrations/006_add_fecha_evento.sql` en Supabase y luego registra "
            "la fecha de cada evento en «Artistas y eventos»."
        )
        return

    sin_fecha = int(datos.get("eventos_sin_fecha") or 0)
    if sin_fecha:
        st.caption(
            f"{sin_fecha} evento(s) no tienen fecha de presentación y no se "
            "incluyen. Complétala en «Artistas y eventos»."
        )

    visitas = datos.get("visitas") or []
    if not visitas:
        mostrar_vacio(
            "No hay presentaciones de artistas en el período seleccionado. "
            "Registra la fecha de cada evento en «Artistas y eventos»."
        )
        if st.button("Ir a Artistas y eventos", key="rent_ir_eventos"):
            go("eventos")
        return

    dias_normales = int(datos.get("dias_normales") or 0)
    metric_grid(
        [
            {
                "label": "Presentaciones calculadas",
                "value": fmt_cantidad(datos.get("visitas_calculadas")),
                "hint": f"De {len(visitas)} en el período, con ventas importadas ese día.",
                "tone": "wine",
            },
            {
                "label": "Ganancia del día",
                "value": _clp(datos.get("ganancia_dia_total")),
                "hint": "Utilidad estimada de esos días menos el costo de los artistas.",
                "tone": "green",
            },
            {
                "label": "Ganancia vs. día normal",
                "value": _clp(datos.get("ganancia_vs_normal_total")),
                "hint": "Lo que los artistas dejaron por sobre un día sin evento.",
                "tone": "default",
            },
            {
                "label": "Ventas de un día normal",
                "value": _clp(datos.get("promedio_ventas_dia_normal")),
                "hint": (
                    f"Promedio de {dias_normales} día(s) sin evento del período."
                    if dias_normales
                    else "No hay días sin evento para comparar."
                ),
                "tone": "muted",
            },
        ]
    )

    st.markdown(
        '<div class="ink-data-note">'
        "<b>Ganancia del día</b> = utilidad estimada de las ventas de FUDO de esa "
        "fecha − costo del artista. <b>Ganancia vs. día normal</b> = (utilidad "
        "del día − utilidad promedio de los días sin evento) − costo del artista: "
        "es lo que el artista aporta por sobre un día corriente. La utilidad usa "
        "el costo base actual y solo las ventas con producto vinculado; si un día "
        "tiene muchas ventas sin vincular, la utilidad queda subestimada. Las "
        "ventas después de medianoche se registran con la fecha siguiente."
        "</div>",
        unsafe_allow_html=True,
    )

    por_artista = datos.get("por_artista") or []
    graficables = [fila for fila in por_artista if fila.get("ganancia_dia") is not None]
    if graficables:
        st.markdown("**Ganancia del día por artista**")
        grafico = pd.DataFrame(
            [
                {
                    "Artista": str(fila.get("artista")),
                    "Ganancia del día": float(fila.get("ganancia_dia") or 0),
                }
                for fila in graficables
            ]
        )
        st.bar_chart(
            grafico.set_index("Artista"),
            horizontal=True,
            color="#800020",
            height=max(160, 56 * len(graficables) + 60),
            width="stretch",
        )

    with st.expander("Resumen por artista", expanded=True):
        st.markdown(_tabla_por_artista(por_artista), unsafe_allow_html=True)
        st.caption(
            "«Pago artista» = costo del artista. «Ganancia» = ganancia del día. "
            "«vs. normal» = diferencia frente al promedio de un día sin evento."
        )
        if any(fila.get("parcial") for fila in por_artista):
            st.caption(
                "«Parcial»: parte de las ventas de ese día no tiene producto "
                "vinculado o costo base, así que su utilidad no se pudo estimar "
                "y la ganancia aparece menor. Vincúlalas en «Ventas de FUDO»."
            )
    with st.expander(f"Detalle por presentación ({len(visitas)})", expanded=False):
        st.markdown(_tabla_visitas(visitas), unsafe_allow_html=True)


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

    hoy = hoy_chile()
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

    st.markdown("---")
    _seccion_artistas(resumen.get("artistas"), evento_filtro is not None)

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
