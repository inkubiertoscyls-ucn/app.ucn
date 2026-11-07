"""Pantalla unificada de movimientos de inventario.

La importación desde Excel es la vía principal: permite cargar varios
movimientos con vista previa y confirmación. El registro manual queda como
alternativa para movimientos puntuales. Ambos usan las mismas validaciones y
el mismo stock calculado desde el historial. Un operario solo opera y consulta
su área; el administrador puede elegir cualquier área.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from data.catalogos import area_id, listar_areas, listar_tipos_movimiento
from data.errors import ErrorDatos
from data.inventario import stock_actual
from data.movimientos import historial_movimientos, registrar_movimiento
from data.permisos import ADMINISTRADOR
from data.productos import listar_productos
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import (
    area_visible,
    fmt_cantidad,
    fmt_clp,
    fmt_fecha_hora,
    fmt_fecha_larga,
)
from ui.layout import page_header, status_badge
from views.importacion_inventario import render_importacion_inventario

TONOS_TIPO = {
    "entrada": "green",
    "salida": "red",
    "merma": "amber",
    "ajuste positivo": "green",
    "ajuste negativo": "red",
}


def _nombre_producto(producto: Dict[str, Any]) -> str:
    nombre = str(producto.get("nombre_producto") or "Sin nombre").strip()
    categoria = str(producto.get("categoria") or "").strip()
    return f"{nombre} · {categoria}" if categoria else nombre


def _costo_inicial(producto: Dict[str, Any]) -> float:
    """Costo base del producto como valor inicial del formulario."""
    try:
        costo = float(producto.get("costo_base") or 0)
    except (TypeError, ValueError):
        return 0.0
    return costo if costo >= 0 else 0.0


def _tono_tipo(tipo: str, factor: int) -> str:
    return TONOS_TIPO.get(tipo.strip().casefold(), "green" if factor > 0 else "red")


def _consumir_confirmacion() -> None:
    confirmacion = st.session_state.pop("mov_confirmacion", None)
    if confirmacion:
        st.success(str(confirmacion))


def _reset_formulario() -> None:
    if st.session_state.pop("mov_reset", False):
        st.session_state.pop("mov_cantidad", None)
        st.session_state.pop("mov_observacion", None)


def _preview_stock(
    stock: float,
    cantidad: int,
    factor: int,
    unidad: str,
    nombre_area: str,
) -> None:
    resultante = stock + (factor * cantidad)
    signo = "+" if factor > 0 else "−"
    clase = "ink-stock-preview-value--danger" if resultante < 0 else "ink-stock-preview-value--ok"
    unidad_texto = f" {unidad}" if unidad else ""

    st.markdown(
        '<div class="ink-stock-preview">'
        "<div>"
        '<div class="ink-stock-preview-label">Stock actual en '
        f"{escape(nombre_area)}</div>"
        f'<div class="ink-stock-preview-value">{escape(fmt_cantidad(stock))}'
        f"{escape(unidad_texto)}</div>"
        "</div>"
        "<div>"
        '<div class="ink-stock-preview-label">Después del movimiento</div>'
        f'<div class="ink-stock-preview-value {clase}">'
        f"{escape(fmt_cantidad(resultante))}{escape(unidad_texto)}</div>"
        f'<div class="ink-stock-preview-detail">{escape(signo)}'
        f"{escape(fmt_cantidad(cantidad))}{escape(unidad_texto)}</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if resultante < 0:
        st.warning(
            "La cantidad supera el stock disponible en el área. "
            "El movimiento será rechazado hasta ajustar la cantidad."
        )


def _render_registro(
    user: Dict[str, Any],
    productos: List[Dict[str, Any]],
    tipos: List[Dict[str, Any]],
    areas: List[Dict[str, Any]],
    es_admin: bool,
) -> None:
    if not productos:
        mostrar_vacio(
            "No hay productos activos para registrar movimientos. "
            "Cuando existan productos en Administración, podrás registrar "
            "entradas, salidas, mermas y ajustes."
        )
        return
    if not tipos:
        mostrar_vacio(
            "No hay tipos de movimiento activos en el catálogo. "
            "Contacta al administrador para habilitarlos."
        )
        return

    area_fija = area_visible(user.get("area_asignada"))

    if es_admin:
        area_elegida = st.selectbox(
            "Área del movimiento",
            areas,
            index=None,
            placeholder="Selecciona un área para continuar",
            format_func=lambda area: str(area.get("nombre_area") or "Sin nombre"),
            key="mov_area",
        )
        if area_elegida is None:
            st.info(
                "Selecciona el área del movimiento. El administrador debe "
                "indicar en qué área se registra cada entrada, salida, merma o ajuste."
            )
            return
        id_area = int(area_elegida.get("id_area"))
        nombre_area = str(area_elegida.get("nombre_area") or "Sin área")
    else:
        id_area = area_id(area_fija, areas)
        nombre_area = area_fija or "Área no asignada"
        st.markdown(
            '<div class="ink-data-note">'
            f"Registrarás el movimiento en tu área asignada: "
            f"<strong>{escape(nombre_area)}</strong>. "
            "No es posible elegir otra área."
            "</div>",
            unsafe_allow_html=True,
        )

    tipo_elegido = st.selectbox(
        "Tipo de movimiento",
        tipos,
        format_func=lambda tipo: str(tipo.get("tipo_movimiento") or "Sin tipo"),
        key="mov_tipo",
    )
    id_tipo = int(tipo_elegido.get("id_tipo_movimiento"))
    nombre_tipo = str(tipo_elegido.get("tipo_movimiento") or "Movimiento")
    try:
        factor = int(tipo_elegido.get("factor_stock"))
    except (TypeError, ValueError):
        factor = 0

    producto = st.selectbox(
        "Producto",
        productos,
        format_func=_nombre_producto,
        key="mov_producto",
    )
    id_producto = int(producto.get("id_producto"))
    unidad = str(producto.get("unidad_medida") or "").strip()

    col_cantidad, col_costo, col_fecha = st.columns([1, 1, 1.2])
    with col_cantidad:
        cantidad = st.number_input(
            "Cantidad",
            min_value=0,
            step=1,
            value=0,
            format="%d",
            key="mov_cantidad",
            help="La cantidad debe ser un entero mayor que cero.",
        )
    with col_costo:
        costo_unitario = st.number_input(
            "Costo unitario (CLP)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            value=_costo_inicial(producto),
            key=f"mov_costo_{id_producto}",
            help=(
                "Costo por unidad. Se inicia con el costo base del producto y "
                "queda guardado en el movimiento."
            ),
        )
    with col_fecha:
        st.text_input(
            "Fecha del movimiento",
            value=fmt_fecha_larga(date.today()),
            disabled=True,
            key="mov_fecha",
        )

    observacion = st.text_area(
        "Observaciones",
        placeholder="Opcional: motivo, proveedor, evento o detalle del ajuste.",
        key="mov_observacion",
    )

    with cargando("Calculando stock del área…"):
        try:
            stock = stock_actual(id_producto, id_area, usuario=user)
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo="No se pudo consultar el stock del área.")
            return

    _preview_stock(stock, int(cantidad), factor, unidad, nombre_area)

    rut = str(user.get("rut_usuario") or "").strip()
    nombre_usuario = str(user.get("nombre_usuario") or "Usuario").strip()
    st.caption(f"Responsable: {nombre_usuario} · {rut or 'sin RUT'}")

    if st.button(
        f"Registrar {nombre_tipo.lower()}",
        key="mov_registrar",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("Registrando movimiento…"):
                resultado = registrar_movimiento(
                    id_producto=id_producto,
                    id_tipo_movimiento=id_tipo,
                    cantidad=cantidad,
                    id_area=id_area,
                    costo_unitario=costo_unitario,
                    observacion=observacion,
                    usuario=user,
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo="No se pudo registrar el movimiento.")
            return

        signo = "+" if resultado["factor"] > 0 else "−"
        unidad_texto = f" {resultado['unidad']}" if resultado["unidad"] else ""
        st.session_state["mov_confirmacion"] = (
            f"Movimiento registrado · {resultado['tipo']}: {signo}"
            f"{fmt_cantidad(resultado['cantidad'])}{unidad_texto} de "
            f"{resultado['producto']} en {resultado['area']}. "
            f"Stock actualizado: {fmt_cantidad(resultado['stock_nuevo'])}"
            f"{unidad_texto}. "
            f"Costo unitario: {fmt_clp(resultado.get('costo_unitario'))}."
        )
        st.session_state["mov_reset"] = True
        st.rerun()


def _tabla_historial(filas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in filas:
        factor = int(fila.get("factor") or 0)
        cantidad = float(fila.get("cantidad") or 0)
        signo = "+" if factor > 0 else "−" if factor < 0 else ""
        clase = "is-pos" if factor > 0 else "is-neg" if factor < 0 else ""
        unidad = str(fila.get("unidad") or "")
        unidad_texto = f" {unidad}" if unidad else ""
        observacion = str(fila.get("observacion") or "").strip() or "—"
        usuario = str(fila.get("usuario") or "Sin usuario")
        rut = str(fila.get("rut_usuario") or "")
        rut_html = (
            f'<div class="ink-muted">{escape(rut)}</div>' if rut else ""
        )
        costo_unitario = fila.get("costo_unitario")

        cuerpo.append(
            "<tr>"
            f'<td class="is-date">{escape(fmt_fecha_hora(fila.get("fecha_hora")))}</td>'
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("producto") or "—"))}</span></td>'
            f"<td>{status_badge(fila.get('tipo'), _tono_tipo(str(fila.get('tipo') or ''), factor))}</td>"
            f'<td class="is-num"><span class="ink-delta {clase}">{escape(signo)}'
            f'{escape(fmt_cantidad(cantidad))}{escape(unidad_texto)}</span></td>'
            f'<td class="is-num">'
            f'{escape(fmt_clp(costo_unitario) if costo_unitario is not None else "—")}'
            "</td>"
            f"<td>{escape(str(fila.get('area') or 'Sin área'))}</td>"
            f'<td><span class="ink-product-name">{escape(usuario)}</span>'
            f"{rut_html}</td>"
            f'<td class="ink-muted">{escape(observacion)}</td>'
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Fecha</th><th>Producto</th><th>Tipo</th>"
        "<th class='is-num'>Cantidad</th><th class='is-num'>Costo unit.</th>"
        "<th>Área</th><th>Responsable</th><th>Observación</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _render_historial(
    user: Dict[str, Any],
    productos: List[Dict[str, Any]],
    tipos: List[Dict[str, Any]],
    areas: List[Dict[str, Any]],
    es_admin: bool,
) -> None:
    st.caption(
        "Movimientos reales registrados. Las cantidades muestran el signo "
        "según el factor de stock del tipo de movimiento."
    )

    col_desde, col_hasta, col_todo = st.columns([1, 1, 1])
    hoy = date.today()
    with col_desde:
        desde = st.date_input(
            "Desde",
            value=hoy - timedelta(days=30),
            key="hist_desde",
        )
    with col_hasta:
        hasta = st.date_input("Hasta", value=hoy, key="hist_hasta")
    with col_todo:
        st.write("")
        todo = st.checkbox(
            "Ver todo el historial",
            key="hist_todo",
            help="Ignora el rango de fechas y consulta los últimos movimientos.",
        )

    col_producto, col_tipo, col_area = st.columns([2, 1.3, 1.3])
    with col_producto:
        producto_filtro = st.selectbox(
            "Producto",
            [None] + productos,
            format_func=lambda producto: (
                "Todos los productos"
                if producto is None
                else _nombre_producto(producto)
            ),
            key="hist_producto",
        )
    with col_tipo:
        tipo_filtro = st.selectbox(
            "Tipo",
            [None] + tipos,
            format_func=lambda tipo: (
                "Todos los tipos"
                if tipo is None
                else str(tipo.get("tipo_movimiento") or "Sin tipo")
            ),
            key="hist_tipo",
        )

    area_filtro = None
    if es_admin:
        with col_area:
            area_sel = st.selectbox(
                "Área",
                [None] + areas,
                format_func=lambda area: (
                    "Todas las áreas"
                    if area is None
                    else str(area.get("nombre_area") or "Sin área")
                ),
                key="hist_area",
            )
            if area_sel is not None:
                area_filtro = int(area_sel.get("id_area"))

    texto = st.text_input(
        "Buscar en el historial",
        placeholder="Producto, categoría, área, tipo, responsable u observación",
        key="hist_texto",
    )

    id_producto = (
        int(producto_filtro.get("id_producto"))
        if producto_filtro is not None
        else None
    )
    id_tipo = (
        int(tipo_filtro.get("id_tipo_movimiento"))
        if tipo_filtro is not None
        else None
    )

    try:
        with cargando("Cargando historial…"):
            filas = historial_movimientos(
                desde=None if todo else desde,
                hasta=None if todo else hasta,
                id_producto=id_producto,
                id_tipo_movimiento=id_tipo,
                id_area=area_filtro,
                texto=texto,
                limite=300,
                usuario=user,
            )
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo cargar el historial.")
        boton_reintentar("historial")
        return

    if not filas:
        rango_por_defecto = (
            not todo
            and desde == hoy - timedelta(days=30)
            and hasta == hoy
        )
        hay_filtros = bool(
            (texto or "").strip()
            or producto_filtro is not None
            or tipo_filtro is not None
            or area_filtro is not None
            or not rango_por_defecto
        )
        if hay_filtros:
            mostrar_vacio(
                "No hay movimientos que coincidan con los filtros. "
                "Prueba con otro rango de fechas, producto o término de búsqueda."
            )
        else:
            mostrar_vacio(
                "Aún no hay movimientos registrados. Cuando se registren "
                "entradas, salidas, mermas o ajustes, aparecerán aquí con su "
                "fecha, responsable y observaciones."
            )
        return

    st.markdown(
        '<div class="ink-table-meta">'
        f"<span>{len(filas)} movimiento(s)</span>"
        f"<span>{'Vista global · todas las áreas' if es_admin else 'Vista de tu área'}</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_tabla_historial(filas), unsafe_allow_html=True)
    if len(filas) >= 300:
        st.caption(
            "Se muestran los 300 movimientos más recientes. Acota el rango de "
            "fechas para ver otros resultados."
        )


def render_movimientos() -> None:
    """Renderiza el registro y el historial de movimientos."""
    user = st.session_state.get("user") or {}
    es_admin = user.get("rol") == ADMINISTRADOR
    area = area_visible(user.get("area_asignada"))

    if es_admin:
        page_header(
            "Movimientos",
            "Importa movimientos desde Excel o registra entradas, salidas, "
            "mermas y ajustes manualmente.",
        )
        alcance = "Vista global · todas las áreas"
    else:
        subtitulo = (
            "Importa movimientos desde Excel o registra uno manualmente en "
            f"tu área · {area}"
            if area
            else "Importa o registra los movimientos de tu área"
        )
        page_header("Movimientos", subtitulo)
        alcance = f"Tu área · {area}" if area else "Área no asignada"

    st.markdown(
        f'<div class="ink-scope">{escape(alcance)}</div>',
        unsafe_allow_html=True,
    )
    _consumir_confirmacion()
    _reset_formulario()

    if not es_admin and not area:
        mostrar_error(
            AuthorizationError(
                "Tu cuenta no tiene un área válida asignada. Contacta al administrador."
            )
        )
        return

    try:
        with cargando("Cargando catálogos…"):
            productos = listar_productos(solo_activos=True)
            tipos = listar_tipos_movimiento()
            areas = listar_areas()
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar los catálogos.")
        boton_reintentar("movimientos")
        return

    opciones_vista = [
        "Importar movimientos (Excel)",
        "Registrar movimiento manual",
        "Historial",
    ]
    vista = st.radio(
        "Vista",
        opciones_vista,
        horizontal=True,
        label_visibility="collapsed",
        key="mov_vista",
    )

    if vista == "Importar movimientos (Excel)":
        render_importacion_inventario(user)
    elif vista == "Registrar movimiento manual":
        if es_admin and not areas:
            mostrar_vacio(
                "No hay áreas activas para registrar movimientos. "
                "Contacta al administrador."
            )
            return
        st.caption(
            "Alternativa secundaria para registrar un movimiento puntual. "
            "Para cargas masivas usa «Importar movimientos (Excel)»."
        )
        _render_registro(user, productos, tipos, areas, es_admin)
    else:
        _render_historial(user, productos, tipos, areas, es_admin)
