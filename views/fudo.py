"""Pantalla de Ventas de FUDO.

Tres pestañas: importación guiada con confirmación explícita, vinculación
manual de productos pendientes y consulta de ventas recientes. No muestra
`datos_raw` en las tablas y no vincula productos ni eventos automáticamente.
"""
from __future__ import annotations

import hashlib
import unicodedata
from datetime import date, timedelta
from html import escape
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from core.exceptions import AuthorizationError
from data.catalogos import listar_eventos
from data.errors import ErrorDatos
from data.fudo import importar_ventas, inspeccionar_archivo, previsualizar_importacion
from data.permisos import ADMINISTRADOR
from data.productos import listar_productos
from data.ventas import listar_ventas, vincular_ventas_por_nombre
from services.fudo_import import CAMPOS_DESTINO, CAMPOS_REQUERIDOS
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_cantidad, fmt_clp, fmt_fecha, fmt_fecha_hora
from ui.layout import metric_grid, page_header, status_badge
from ui.state import flash, go, render_flash

SUGERENCIAS = {
    "fecha_venta": ("fecha", "date", "dia"),
    "total_venta": ("total", "monto", "importe", "valor"),
    "cantidad_total": ("cantidad", "qty", "unidades", "unidad"),
    "producto_identificado": (
        "producto",
        "item",
        "articulo",
        "descripcion",
        "detalle",
        "nombre",
    ),
}

ESTADOS_ANALISIS = {
    "valido": ("Válido", "green"),
    "error": ("Error", "red"),
    "duplicado": ("Duplicado", "amber"),
}


def _normalizar(texto: Any) -> str:
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", str(texto or ""))
        if not unicodedata.combining(caracter)
    )
    return " ".join(sin_acentos.casefold().split())


def _sugerir_columna(
    campo: str,
    columnas: List[str],
    usadas: set[str],
) -> int:
    claves = SUGERENCIAS.get(campo, ())
    candidatas = [col for col in columnas if col not in usadas]
    for columna in candidatas:
        if _normalizar(columna) == _normalizar(CAMPOS_DESTINO[campo]):
            return columnas.index(columna) + 1
    for columna in candidatas:
        normalizada = _normalizar(columna)
        if any(clave in normalizada for clave in claves):
            return columnas.index(columna) + 1
    return 0


def _limpiar_archivo() -> None:
    for clave in (
        "fudo_firma",
        "fudo_archivo",
        "fudo_inspeccion",
        "fudo_analisis",
        "fudo_analisis_firma",
        "fudo_error",
        "fudo_confirmar",
    ):
        st.session_state.pop(clave, None)
    st.session_state["fudo_upload_id"] = int(
        st.session_state.get("fudo_upload_id", 0)
    ) + 1


def _tabla_detalle(filas: List[Dict[str, Any]], *, con_registro: bool = True) -> str:
    cuerpo = []
    for fila in filas:
        registro = (
            f'<td class="is-num">{escape(str(fila.get("registro") or "—"))}</td>'
            if con_registro
            else ""
        )
        cuerpo.append(
            "<tr>"
            f"{registro}"
            f'<td>{escape(str(fila.get("producto") or "—"))}</td>'
            f'<td class="is-date">{escape(str(fila.get("fecha") or "—"))}</td>'
            f'<td>{escape(str(fila.get("detalle") or "—"))}</td>'
            "</tr>"
        )
    cabecera = "<th>Registro</th>" if con_registro else ""
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        f"<thead><tr>{cabecera}<th>Producto</th><th>Fecha</th>"
        "<th>Detalle</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_analisis(filas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in filas:
        estado = str(fila.get("estado") or "")
        etiqueta, tono = ESTADOS_ANALISIS.get(estado, ("—", "muted"))
        cantidad = fila.get("cantidad")
        total = fila.get("total")
        cuerpo.append(
            "<tr>"
            f'<td class="is-num">{escape(str(fila.get("registro") or "—"))}</td>'
            f'<td class="is-date">{escape(fmt_fecha(fila.get("fecha")))}</td>'
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("producto") or "—"))}</span></td>'
            f'<td class="is-num">{escape(fmt_cantidad(cantidad) if cantidad is not None else "—")}</td>'
            f'<td class="is-num">{escape(fmt_clp(total) if total is not None else "—")}</td>'
            f"<td>{status_badge(etiqueta, tono)}</td>"
            f'<td class="ink-muted">{escape(str(fila.get("detalle") or "—"))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Registro</th><th>Fecha</th><th>Producto</th>"
        "<th class='is-num'>Cantidad</th><th class='is-num'>Total</th>"
        "<th>Estado</th><th>Detalle</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_pendientes(grupos: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for grupo in grupos:
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(grupo.get("producto") or "—"))}</span></td>'
            f'<td class="is-num">{escape(fmt_cantidad(grupo.get("ventas")))}</td>'
            f'<td class="is-num">{escape(fmt_clp(grupo.get("total")))}</td>'
            f'<td class="is-date">{escape(fmt_fecha(grupo.get("ultima_fecha")))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Producto informado por FUDO</th>"
        "<th class='is-num'>Ventas pendientes</th>"
        "<th class='is-num'>Total informado</th>"
        "<th>Última venta</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_ventas(
    filas: List[Dict[str, Any]],
    productos: Dict[int, Dict[str, Any]],
    eventos: Dict[int, str],
) -> str:
    cuerpo = []
    for fila in filas:
        id_producto = fila.get("id_producto_relacionado")
        try:
            id_producto_int = int(id_producto) if id_producto is not None else None
        except (TypeError, ValueError):
            id_producto_int = None
        producto = productos.get(id_producto_int) if id_producto_int else None
        if producto:
            vinculacion = status_badge(
                str(producto.get("nombre_producto") or "Vinculado"), "green"
            )
        else:
            vinculacion = status_badge("Pendiente", "amber")

        id_evento = fila.get("id_evento")
        try:
            id_evento_int = int(id_evento) if id_evento is not None else None
        except (TypeError, ValueError):
            id_evento_int = None
        evento_texto = (
            eventos.get(id_evento_int, f"Evento {id_evento_int}")
            if id_evento_int is not None
            else "Sin evento"
        )

        cantidad = fila.get("cantidad_total")
        cuerpo.append(
            "<tr>"
            f'<td class="is-date">{escape(fmt_fecha(fila.get("fecha_venta")))}</td>'
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("producto_identificado") or "—"))}</span>'
            f'<div class="ink-muted">{escape(str(fila.get("origen_archivo") or "—"))}</div>'
            "</td>"
            f'<td class="is-num">{escape(fmt_cantidad(cantidad) if cantidad is not None else "—")}</td>'
            f'<td class="is-num">{escape(fmt_clp(fila.get("total_venta")))}</td>'
            f"<td>{escape(evento_texto)}</td>"
            f"<td>{vinculacion}</td>"
            f'<td class="is-date">{escape(fmt_fecha_hora(fila.get("fecha_importacion")))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Fecha</th><th>Producto FUDO</th>"
        "<th class='is-num'>Cantidad</th><th class='is-num'>Total</th>"
        "<th>Evento registrado</th><th>Producto vinculado</th>"
        "<th>Importado</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _mostrar_resultado() -> None:
    resultado = st.session_state.get("fudo_resultado")
    if not resultado:
        return

    st.success(
        "Importación finalizada. Los registros válidos fueron guardados en "
        "la base de datos."
    )
    metric_grid(
        [
            {
                "label": "Importados",
                "value": fmt_cantidad(resultado.get("importados")),
                "hint": "Ventas nuevas guardadas.",
                "tone": "green",
            },
            {
                "label": "Rechazados",
                "value": fmt_cantidad(resultado.get("rechazados")),
                "hint": "Con errores de fecha, monto, cantidad o producto.",
                "tone": "red",
            },
            {
                "label": "Duplicados",
                "value": fmt_cantidad(resultado.get("duplicados")),
                "hint": "Ya existían o repetían datos dentro del archivo.",
                "tone": "amber",
            },
            {
                "label": "Filas vacías",
                "value": fmt_cantidad(resultado.get("filas_vacias")),
                "hint": "No contenían datos y no se consideraron.",
                "tone": "muted",
            },
        ]
    )
    st.caption(
        f"Archivo: {resultado.get('nombre_archivo') or '—'}"
        + (
            f" · Hoja: {resultado.get('hoja')}"
            if resultado.get("hoja")
            else ""
        )
    )

    errores = resultado.get("errores") or []
    if errores:
        st.markdown("**Registros no importados**")
        st.markdown(
            _tabla_detalle(errores[:200]),
            unsafe_allow_html=True,
        )
        if len(errores) > 200:
            st.caption("Se muestran los primeros 200 registros con problemas.")

    advertencias = resultado.get("detalle_advertencias") or []
    if advertencias:
        with st.expander(f"Advertencias ({len(advertencias)})"):
            st.markdown(
                _tabla_detalle(advertencias[:200]),
                unsafe_allow_html=True,
            )

    if st.button("Importar otro archivo", key="fudo_otro"):
        st.session_state.pop("fudo_resultado", None)
        st.rerun()


def _render_importar(user: Dict[str, Any]) -> None:
    _mostrar_resultado()
    if st.session_state.get("fudo_resultado"):
        return

    if st.session_state.get("fudo_archivo"):
        col_nombre, col_quitar = st.columns([4, 1])
        with col_nombre:
            st.markdown(
                '<div class="ink-data-note">'
                "Archivo cargado: "
                f"<strong>{escape(str(st.session_state['fudo_archivo'].get('nombre') or '—'))}</strong>"
                "</div>",
                unsafe_allow_html=True,
            )
        with col_quitar:
            if st.button("Quitar archivo", key="fudo_quitar", use_container_width=True):
                _limpiar_archivo()
                st.rerun()

    upload_id = int(st.session_state.get("fudo_upload_id", 0))
    archivo = st.file_uploader(
        "Archivo exportado desde FUDO",
        type=["csv", "xlsx", "xls"],
        key=f"fudo_upload_{upload_id}",
        help="Formatos aceptados: CSV, XLSX y XLS. Tamaño máximo: 25 MB.",
    )

    if archivo is not None:
        contenido = archivo.getvalue()
        firma = hashlib.sha256(contenido).hexdigest() + ":" + archivo.name
        if firma != st.session_state.get("fudo_firma"):
            with st.spinner("Revisando el archivo…"):
                try:
                    inspeccion = inspeccionar_archivo(
                        contenido, archivo.name, usuario=user
                    )
                except (ErrorDatos, AuthorizationError) as exc:
                    st.session_state["fudo_firma"] = firma
                    st.session_state["fudo_error"] = str(
                        getattr(exc, "mensaje", exc)
                    )
                else:
                    st.session_state["fudo_firma"] = firma
                    st.session_state["fudo_archivo"] = {
                        "nombre": archivo.name,
                        "contenido": contenido,
                    }
                    st.session_state["fudo_inspeccion"] = inspeccion
                    st.session_state.pop("fudo_error", None)
                    st.session_state.pop("fudo_analisis", None)
                    st.session_state.pop("fudo_analisis_firma", None)
            st.rerun()

    error_archivo = st.session_state.get("fudo_error")
    if error_archivo:
        st.error(str(error_archivo))
        if st.button("Reintentar lectura", key="fudo_reintentar"):
            st.session_state.pop("fudo_error", None)
            st.session_state.pop("fudo_firma", None)
            st.rerun()
        return

    guardado = st.session_state.get("fudo_archivo")
    inspeccion = st.session_state.get("fudo_inspeccion")
    if not guardado or not inspeccion:
        st.caption(
            "Carga un archivo para revisar sus hojas, columnas y una muestra "
            "antes de importar. Nada se guarda hasta que confirmes."
        )
        return

    contenido = guardado.get("contenido")
    nombre_archivo = str(guardado.get("nombre") or "archivo FUDO")
    firma_corta = str(st.session_state.get("fudo_firma") or "")[:12]

    hojas = list(inspeccion.get("hojas") or [])
    if inspeccion.get("tipo") == "csv":
        hoja = "csv"
        st.caption("Archivo CSV. Se usará como una única tabla.")
    else:
        if not hojas:
            st.error("El archivo Excel no contiene hojas legibles.")
            return
        hoja = st.selectbox(
            "Hoja del archivo",
            hojas,
            key=f"fudo_hoja_{firma_corta}",
        )

    columnas = list(
        (inspeccion.get("columnas_por_hoja") or {}).get(hoja) or []
    )
    columnas = [str(columna) for columna in columnas]
    if not columnas:
        st.error("La hoja seleccionada no tiene columnas para revisar.")
        return

    with st.expander("Vista previa del archivo original", expanded=False):
        muestra = (inspeccion.get("preview") or {}).get(hoja) or []
        if muestra:
            st.dataframe(
                pd.DataFrame(muestra),
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Se muestran las primeras 10 filas del archivo.")
        else:
            st.caption("La hoja no tiene filas para mostrar.")

    st.markdown("**Mapeo de columnas**")
    st.caption(
        "Relaciona las columnas del archivo con los campos de INKubiertos. "
        "La fecha, el total y el producto son obligatorios. La cantidad es "
        "opcional, pero sin ella no se puede estimar el costo."
    )

    usadas: set[str] = set()
    mapeo: Dict[str, str] = {}
    for campo, etiqueta in CAMPOS_DESTINO.items():
        obligatorio = campo in CAMPOS_REQUERIDOS
        opciones = [""] + columnas
        indice = _sugerir_columna(campo, columnas, usadas)
        seleccion = st.selectbox(
            f"{etiqueta}{' *' if obligatorio else ' (opcional)'}",
            opciones,
            index=indice,
            format_func=lambda valor: (
                "— Sin asignar —" if valor == "" else str(valor)
            ),
            key=f"fudo_map_{campo}_{hoja}_{firma_corta}",
        )
        if seleccion:
            mapeo[str(seleccion)] = campo
            usadas.add(str(seleccion))

    faltantes = [
        CAMPOS_DESTINO[campo]
        for campo in CAMPOS_REQUERIDOS
        if campo not in mapeo.values()
    ]
    if faltantes:
        st.info(
            "Falta asignar: " + ", ".join(faltantes) + ". "
            "Completa el mapeo para validar el archivo."
        )

    firma_analisis = (firma_corta, hoja, tuple(sorted(mapeo.items())))
    if st.button(
        "Validar y previsualizar",
        key="fudo_validar",
        type="primary",
        disabled=bool(faltantes),
        use_container_width=True,
    ):
        try:
            with st.spinner("Validando fechas, montos, cantidades y duplicados…"):
                analisis = previsualizar_importacion(
                    contenido,
                    nombre_archivo,
                    hoja=hoja,
                    mapeo=mapeo,
                    usuario=user,
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo="No se pudo validar el archivo.")
        else:
            st.session_state["fudo_analisis"] = {
                "total_filas": analisis.get("total_filas"),
                "filas_vacias": analisis.get("filas_vacias"),
                "total_consideradas": analisis.get("total_consideradas"),
                "validos": analisis.get("validos"),
                "con_error": analisis.get("con_error"),
                "duplicados": analisis.get("duplicados"),
                "advertencias": analisis.get("advertencias"),
                "importables": analisis.get("importables"),
                "filas": list(analisis.get("filas") or [])[:300],
                "errores": list(analisis.get("errores") or [])[:300],
                "detalle_advertencias": list(
                    analisis.get("detalle_advertencias") or []
                )[:300],
                "advertencias_generales": list(
                    analisis.get("advertencias_generales") or []
                ),
                "nombre_archivo": analisis.get("nombre_archivo"),
                "hoja": analisis.get("hoja"),
            }
            st.session_state["fudo_analisis_firma"] = firma_analisis
            st.session_state.pop("fudo_confirmar", None)
            st.rerun()

    analisis = st.session_state.get("fudo_analisis")
    if not analisis:
        return
    if st.session_state.get("fudo_analisis_firma") != firma_analisis:
        st.warning(
            "El archivo, la hoja o el mapeo cambiaron. Vuelve a validar antes "
            "de confirmar la importación."
        )
        return

    _render_analisis(user, contenido, nombre_archivo, hoja, mapeo, analisis)


def _render_analisis(
    user: Dict[str, Any],
    contenido: Any,
    nombre_archivo: str,
    hoja: str,
    mapeo: Dict[str, str],
    analisis: Dict[str, Any],
) -> None:
    st.markdown("---")
    metric_grid(
        [
            {
                "label": "Listos para importar",
                "value": fmt_cantidad(analisis.get("importables")),
                "hint": "Registros válidos y no duplicados.",
                "tone": "green",
            },
            {
                "label": "Con errores",
                "value": fmt_cantidad(analisis.get("con_error")),
                "hint": "No se escribirán hasta corregir el archivo.",
                "tone": "red",
            },
            {
                "label": "Duplicados",
                "value": fmt_cantidad(analisis.get("duplicados")),
                "hint": "Ya existían o se repiten en el archivo.",
                "tone": "amber",
            },
            {
                "label": "Advertencias",
                "value": fmt_cantidad(analisis.get("advertencias")),
                "hint": "Se importan, pero pueden no entrar al costo estimado.",
                "tone": "muted",
            },
        ]
    )

    for advertencia in analisis.get("advertencias_generales") or []:
        st.warning(str(advertencia))

    errores = analisis.get("errores") or []
    if errores:
        with st.expander(
            f"Registros con errores o duplicados ({len(errores)})",
            expanded=True,
        ):
            st.markdown(
                _tabla_detalle(errores[:200]),
                unsafe_allow_html=True,
            )
            if len(errores) > 200:
                st.caption("Se muestran los primeros 200 registros.")

    advertencias = analisis.get("detalle_advertencias") or []
    if advertencias:
        with st.expander(f"Advertencias por registro ({len(advertencias)})"):
            st.markdown(
                _tabla_detalle(advertencias[:200]),
                unsafe_allow_html=True,
            )

    filas = analisis.get("filas") or []
    if filas:
        with st.expander(
            f"Previsualización validada ({len(filas)} registros mostrados)",
            expanded=True,
        ):
            st.markdown(_tabla_analisis(filas), unsafe_allow_html=True)

    importables = int(analisis.get("importables") or 0)
    if importables == 0:
        st.info(
            "No hay registros válidos para importar. Corrige el archivo o "
            "ajusta el mapeo y vuelve a validar."
        )
        return

    confirmado = st.checkbox(
        f"Confirmo que revisé los {fmt_cantidad(importables)} registros y "
        "quiero importarlos a INKubiertos.",
        key="fudo_confirmar",
    )
    st.caption(
        "Solo se guardarán los registros válidos y no duplicados. Los productos "
        "quedarán pendientes de vinculación hasta que los relaciones manualmente."
    )
    if st.button(
        "Confirmar importación",
        key="fudo_importar",
        type="primary",
        disabled=not confirmado,
        use_container_width=True,
    ):
        try:
            with st.spinner("Importando ventas…"):
                resultado = importar_ventas(
                    contenido,
                    nombre_archivo,
                    hoja=hoja,
                    mapeo=mapeo,
                    confirmado=True,
                    usuario=user,
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo="No se pudo completar la importación.")
            return

        st.session_state["fudo_resultado"] = resultado
        _limpiar_archivo()
        st.rerun()


def _agrupar_pendientes(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grupos: Dict[str, Dict[str, Any]] = {}
    for fila in filas:
        nombre = str(fila.get("producto_identificado") or "").strip()
        clave = nombre if nombre else "(Sin nombre de producto)"
        grupo = grupos.setdefault(
            clave,
            {
                "producto": clave,
                "ventas": 0,
                "total": 0.0,
                "ultima_fecha": None,
            },
        )
        grupo["ventas"] += 1
        try:
            grupo["total"] += float(fila.get("total_venta") or 0)
        except (TypeError, ValueError):
            pass
        fecha = fila.get("fecha_venta")
        if fecha and (
            grupo["ultima_fecha"] is None
            or str(fecha) > str(grupo["ultima_fecha"])
        ):
            grupo["ultima_fecha"] = fecha

    lista = list(grupos.values())
    lista.sort(key=lambda grupo: (-grupo["ventas"], grupo["producto"].casefold()))
    return lista


def _render_pendientes(user: Dict[str, Any]) -> None:
    try:
        with cargando("Cargando ventas pendientes…"):
            pendientes = listar_ventas(
                solo_pendientes=True,
                limite=500,
                usuario=user,
            )
            productos = listar_productos(solo_activos=False)
            eventos = {
                int(evento.get("id_evento")): str(
                    evento.get("nombre_evento") or f"Evento {evento.get('id_evento')}"
                )
                for evento in listar_eventos(incluir_inactivos=True)
                if evento.get("id_evento") is not None
            }
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar las ventas pendientes.")
        boton_reintentar("fudo_pendientes")
        return

    st.caption(
        "Estas ventas conservan el nombre de producto informado por FUDO. "
        "La vinculación es manual: no se asignan coincidencias automáticas."
    )

    if not pendientes:
        mostrar_vacio(
            "No hay ventas pendientes de vinculación. Todas las ventas "
            "importadas tienen un producto asignado."
        )
        return

    grupos = _agrupar_pendientes(pendientes)
    st.markdown(
        f'<div class="ink-table-meta"><span>{len(pendientes)} venta(s) '
        f"pendientes en {len(grupos)} producto(s) informado(s)</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(_tabla_pendientes(grupos), unsafe_allow_html=True)

    if not productos:
        st.warning(
            "No hay productos en el catálogo para vincular. Cuando existan "
            "productos en Administración, podrás relacionar estas ventas."
        )
        return

    st.markdown("---")
    st.markdown("**Vincular ventas pendientes**")
    grupo = st.selectbox(
        "Producto informado por FUDO",
        grupos,
        format_func=lambda item: (
            f"{item['producto']} · {item['ventas']} venta(s)"
        ),
        key="fudo_pendiente_grupo",
    )
    producto = st.selectbox(
        "Producto de INKubiertos",
        productos,
        index=None,
        placeholder="Selecciona el producto que corresponde",
        format_func=lambda item: " · ".join(
            parte
            for parte in (
                str(item.get("nombre_producto") or "Sin nombre"),
                str(item.get("categoria") or ""),
            )
            if parte
        ),
        key="fudo_pendiente_producto",
    )

    if grupo:
        st.caption(
            f"Se vincularán {fmt_cantidad(grupo['ventas'])} venta(s) de "
            f"“{grupo['producto']}”. Solo se modificará la relación con el "
            "producto; se conservan el nombre original, las fechas, los montos "
            "y el respaldo del archivo."
        )

    if st.button(
        "Vincular ventas seleccionadas",
        key="fudo_vincular",
        type="primary",
        disabled=producto is None,
        use_container_width=True,
    ):
        try:
            with st.spinner("Vinculando ventas…"):
                resultado = vincular_ventas_por_nombre(
                    grupo["producto"],
                    producto.get("id_producto"),
                    usuario=user,
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo="No se pudo vincular el producto.")
            return

        flash(
            "success",
            f"{fmt_cantidad(resultado['vinculadas'])} venta(s) de "
            f"“{resultado['producto_identificado']}” quedaron vinculadas a "
            f"{resultado['producto']}.",
        )
        st.rerun()

    with st.expander("Ver ventas pendientes una por una"):
        st.markdown(
            _tabla_ventas(pendientes, {}, eventos),
            unsafe_allow_html=True,
        )


def _render_ventas(user: Dict[str, Any]) -> None:
    hoy = date.today()
    col_desde, col_hasta, col_todo = st.columns([1, 1, 1])
    with col_desde:
        desde = st.date_input(
            "Desde",
            value=hoy - timedelta(days=30),
            key="fudo_desde",
        )
    with col_hasta:
        hasta = st.date_input("Hasta", value=hoy, key="fudo_hasta")
    with col_todo:
        st.write("")
        todo = st.checkbox(
            "Ver todas las fechas",
            key="fudo_todo",
            help="Ignora el rango de fechas y consulta las ventas más recientes.",
        )

    texto = st.text_input(
        "Buscar por producto informado por FUDO",
        placeholder="Nombre del producto",
        key="fudo_texto",
    )

    if desde > hasta and not todo:
        st.warning("La fecha desde no puede ser posterior a la fecha hasta.")
        return

    try:
        with cargando("Cargando ventas…"):
            filas = listar_ventas(
                desde=None if todo else desde,
                hasta=None if todo else hasta,
                texto=texto,
                limite=200,
                usuario=user,
            )
            productos = {
                int(producto.get("id_producto")): producto
                for producto in listar_productos(solo_activos=False)
                if producto.get("id_producto") is not None
            }
            eventos = {
                int(evento.get("id_evento")): str(
                    evento.get("nombre_evento") or f"Evento {evento.get('id_evento')}"
                )
                for evento in listar_eventos(incluir_inactivos=True)
                if evento.get("id_evento") is not None
            }
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar las ventas.")
        boton_reintentar("fudo_ventas")
        return

    if not filas:
        mostrar_vacio(
            "No hay ventas importadas para los filtros seleccionados. "
            "Carga un archivo desde la pestaña Importar."
        )
        return

    st.markdown(
        f'<div class="ink-table-meta"><span>{len(filas)} venta(s)</span>'
        "<span>Sin datos originales sensibles</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        _tabla_ventas(filas, productos, eventos),
        unsafe_allow_html=True,
    )
    if len(filas) >= 200:
        st.caption(
            "Se muestran las 200 ventas más recientes. Acota el rango de "
            "fechas o usa la búsqueda para ver otras."
        )


def render_fudo() -> None:
    """Renderiza la importación, la vinculación y las ventas recientes."""
    user = st.session_state.get("user") or {}
    if user.get("rol") != ADMINISTRADOR:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

    page_header(
        "Ventas de FUDO",
        "Importa las ventas exportadas desde FUDO y vincula sus productos.",
    )
    render_flash()
    st.markdown(
        '<div class="ink-scope">Administración · importación de ventas</div>',
        unsafe_allow_html=True,
    )

    tab_importar, tab_pendientes, tab_ventas = st.tabs(
        ["Importar archivo", "Productos pendientes", "Ventas recientes"]
    )
    with tab_importar:
        _render_importar(user)
    with tab_pendientes:
        _render_pendientes(user)
    with tab_ventas:
        _render_ventas(user)

    st.markdown("")
    if st.button("Ir a Rentabilidad", key="fudo_ir_rentabilidad"):
        go("rentabilidad")
