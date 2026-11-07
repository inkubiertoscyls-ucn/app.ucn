"""Importación de movimientos de inventario desde Excel (.xlsx).

Flujo guiado para Administrador y Operario: descarga de plantilla, carga del
archivo, vista previa con filas válidas, errores y duplicados, confirmación
explícita y resumen. Nada se escribe en la base antes de la confirmación.
"""
from __future__ import annotations

import hashlib
from html import escape
from typing import Any, Dict, List

import streamlit as st

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.importacion_inventario import (
    importar_entradas_inventario,
    previsualizar_importacion_inventario,
    generar_plantilla_inventario,
)
from ui.feedback import cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_cantidad, fmt_clp, fmt_fecha
from ui.layout import metric_grid, status_badge

ESTADOS = {
    "valido": ("Válido", "green"),
    "error": ("Error", "red"),
    "duplicado": ("Duplicado", "amber"),
}

EXTENSION = ".xlsx"


def _limpiar_archivo() -> None:
    for clave in (
        "imp_inv_firma",
        "imp_inv_archivo",
        "imp_inv_analisis",
        "imp_inv_error",
        "imp_inv_confirmar",
    ):
        st.session_state.pop(clave, None)
    st.session_state["imp_inv_upload_id"] = int(
        st.session_state.get("imp_inv_upload_id", 0)
    ) + 1


def _tabla_preview(filas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in filas:
        estado = str(fila.get("estado") or "")
        etiqueta, tono = ESTADOS.get(estado, ("—", "muted"))
        cantidad = fila.get("cantidad")
        costo = fila.get("costo_unitario")
        cuerpo.append(
            "<tr>"
            f'<td class="is-num">{escape(str(fila.get("registro") or "—"))}</td>'
            f'<td class="is-date">{escape(fmt_fecha(fila.get("fecha")))}</td>'
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("producto") or "—"))}</span></td>'
            f'<td>{escape(str(fila.get("area") or "—"))}</td>'
            f'<td>{escape(str(fila.get("tipo") or "—"))}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(cantidad) if cantidad is not None else "—")}</td>'
            f'<td class="is-num">{escape(fmt_clp(costo) if costo is not None else "—")}</td>'
            f'<td>{escape(str(fila.get("responsable") or "—"))}</td>'
            f"<td>{status_badge(etiqueta, tono)}</td>"
            f'<td class="ink-muted">{escape(str(fila.get("detalle") or "—"))}</td>'
            "</tr>"
        )
    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th class='is-num'>Fila</th><th>Fecha</th><th>Producto</th>"
        "<th>Área</th><th>Tipo</th><th class='is-num'>Cantidad</th>"
        "<th class='is-num'>Costo unit.</th><th>Responsable</th>"
        "<th>Estado</th><th>Detalle</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _mostrar_resultado() -> None:
    resultado = st.session_state.get("imp_inv_resultado")
    if not resultado:
        return

    st.success(
        "Importación completada. Los movimientos confirmados quedaron "
        "registrados y el inventario ya refleja el stock actualizado."
    )
    metric_grid(
        [
            {
                "label": "Importados",
                "value": fmt_cantidad(resultado.get("importados")),
                "hint": "Movimientos registrados en el inventario.",
                "tone": "green",
            },
            {
                "label": "Rechazados",
                "value": fmt_cantidad(resultado.get("rechazados")),
                "hint": "Filas con errores. No se registraron.",
                "tone": "red",
            },
            {
                "label": "Duplicados",
                "value": fmt_cantidad(resultado.get("duplicados")),
                "hint": "Ya existían o repetían datos del archivo.",
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
    st.caption(f"Archivo: {resultado.get('nombre_archivo') or '—'}")

    errores = resultado.get("errores") or []
    if errores:
        with st.expander(
            f"Filas no importadas ({len(errores)})",
            expanded=True,
        ):
            st.markdown(
                _tabla_preview(
                    [
                        {
                            "registro": error.get("registro"),
                            "fecha": error.get("fecha"),
                            "producto": error.get("producto"),
                            "tipo": error.get("tipo"),
                            "responsable": error.get("responsable"),
                            "estado": (
                                "duplicado"
                                if "duplicad" in str(error.get("detalle") or "").lower()
                                else "error"
                            ),
                            "detalle": error.get("detalle"),
                        }
                        for error in errores[:300]
                    ]
                ),
                unsafe_allow_html=True,
            )
            if len(errores) > 300:
                st.caption("Se muestran las primeras 300 filas.")

    if st.button("Importar otro archivo", key="imp_inv_otro"):
        st.session_state.pop("imp_inv_resultado", None)
        st.rerun()


def _render_preview(
    user: Dict[str, Any],
    contenido: bytes,
    nombre_archivo: str,
    analisis: Dict[str, Any],
) -> None:
    st.markdown("---")
    metric_grid(
        [
            {
                "label": "Listas para importar",
                "value": fmt_cantidad(analisis.get("importables")),
                "hint": "Filas válidas y no duplicadas.",
                "tone": "green",
            },
            {
                "label": "Con errores",
                "value": fmt_cantidad(analisis.get("con_error")),
                "hint": "No se registrarán hasta corregirlas.",
                "tone": "red",
            },
            {
                "label": "Duplicadas",
                "value": fmt_cantidad(analisis.get("duplicados")),
                "hint": "Ya importadas o repetidas en el archivo.",
                "tone": "amber",
            },
            {
                "label": "Filas consideradas",
                "value": fmt_cantidad(analisis.get("total_consideradas")),
                "hint": "Sin contar filas vacías.",
                "tone": "muted",
            },
        ]
    )

    for advertencia in analisis.get("advertencias_generales") or []:
        st.warning(str(advertencia))

    filas = analisis.get("filas") or []
    validas = [fila for fila in filas if fila.get("estado") == "valido"]
    con_problemas = [fila for fila in filas if fila.get("estado") != "valido"]

    if validas:
        with st.expander(
            f"Movimientos válidos ({len(validas)})",
            expanded=True,
        ):
            st.markdown(
                _tabla_preview(validas[:300]),
                unsafe_allow_html=True,
            )
            if len(validas) > 300:
                st.caption("Se muestran las primeras 300 filas válidas.")

    if con_problemas:
        with st.expander(
            f"Filas con errores o duplicadas ({len(con_problemas)})",
            expanded=True,
        ):
            st.markdown(
                _tabla_preview(con_problemas[:300]),
                unsafe_allow_html=True,
            )
            st.caption(
                "Cada fila indica su número y el motivo. Corrige el archivo y "
                "vuelve a cargarlo para incluir esos movimientos."
            )

    if not filas:
        mostrar_vacio(
            "La hoja de movimientos no tiene filas con datos. Agrega los "
            "movimientos y vuelve a cargar el archivo."
        )
        return

    importables = int(analisis.get("importables") or 0)
    if importables == 0:
        st.info(
            "No hay filas válidas para importar. Corrige los errores del "
            "archivo y vuelve a cargarlo."
        )
        return

    confirmado = st.checkbox(
        f"Confirmo que revisé los {fmt_cantidad(importables)} movimientos "
        "válidos y quiero registrarlos en el inventario.",
        key="imp_inv_confirmar",
    )
    st.caption(
        "Solo se registrarán las filas válidas. Los errores y duplicados no se "
        "escribirán. Si una fila falla al guardar, no se registrará ninguna."
    )
    if st.button(
        "Confirmar importación",
        key="imp_inv_importar",
        type="primary",
        disabled=not confirmado,
        use_container_width=True,
    ):
        try:
            with st.spinner("Registrando movimientos de inventario…"):
                resultado = importar_entradas_inventario(
                    contenido,
                    nombre_archivo,
                    confirmado=True,
                    usuario=user,
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo="No se pudo completar la importación.")
            return
        else:
            st.session_state["imp_inv_resultado"] = resultado
            _limpiar_archivo()
            st.rerun()


def _render_plantilla(user: Dict[str, Any]) -> bytes:
    plantilla = st.session_state.get("imp_inv_plantilla")
    if plantilla:
        return plantilla
    try:
        with cargando("Preparando la plantilla con los catálogos actuales…"):
            plantilla = generar_plantilla_inventario(usuario=user)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo preparar la plantilla.")
        return b""
    st.session_state["imp_inv_plantilla"] = plantilla
    return plantilla


def render_importacion_inventario(user: Dict[str, Any]) -> None:
    """Renderiza el flujo de importación para Administrador y Operario."""
    _mostrar_resultado()
    if st.session_state.get("imp_inv_resultado"):
        return

    st.caption(
        "Importa movimientos de inventario desde un archivo Excel .xlsx. "
        "Cada fila es un movimiento independiente: entrada, salida, merma o "
        "ajuste. Si eres Operario, solo se aceptarán filas de tu área. "
        "Primero revisa la vista previa y luego confirma: nada se guarda antes."
    )

    plantilla = _render_plantilla(user)
    if plantilla:
        st.download_button(
            "Descargar plantilla de movimientos",
            data=plantilla,
            file_name="plantilla_movimientos_inventario.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="imp_inv_plantilla_descarga",
            use_container_width=True,
        )

    st.markdown("---")
    guardado = st.session_state.get("imp_inv_archivo")
    if guardado:
        col_nombre, col_quitar = st.columns([4, 1])
        with col_nombre:
            st.markdown(
                '<div class="ink-data-note">'
                "Archivo cargado: "
                f"<strong>{escape(str(guardado.get('nombre') or '—'))}</strong>"
                "</div>",
                unsafe_allow_html=True,
            )
        with col_quitar:
            if st.button(
                "Quitar archivo",
                key="imp_inv_quitar",
                use_container_width=True,
            ):
                _limpiar_archivo()
                st.rerun()

    upload_id = int(st.session_state.get("imp_inv_upload_id", 0))
    archivo = st.file_uploader(
        "Archivo Excel de movimientos",
        type=["xlsx"],
        key=f"imp_inv_upload_{upload_id}",
        help=(
            "Formato .xlsx. Debe incluir las columnas fecha, producto, area, "
            "cantidad y, opcionalmente, tipo_movimiento, costo_unitario, "
            "proveedor, documento, observacion y rut_usuario. También se "
            "acepta la hoja «Movimientos_Registrados_App». Tamaño máximo: 10 MB."
        ),
    )

    if archivo is not None:
        contenido = archivo.getvalue()
        firma = hashlib.sha256(contenido).hexdigest()
        if firma != st.session_state.get("imp_inv_firma"):
            with st.spinner("Validando el archivo…"):
                try:
                    analisis = previsualizar_importacion_inventario(
                        contenido,
                        archivo.name,
                        usuario=user,
                    )
                except (ErrorDatos, AuthorizationError) as exc:
                    st.session_state["imp_inv_firma"] = firma
                    st.session_state["imp_inv_error"] = str(
                        getattr(exc, "mensaje", exc)
                    )
                    st.session_state.pop("imp_inv_archivo", None)
                    st.session_state.pop("imp_inv_analisis", None)
                else:
                    st.session_state["imp_inv_firma"] = firma
                    st.session_state["imp_inv_archivo"] = {
                        "nombre": archivo.name,
                        "contenido": contenido,
                    }
                    st.session_state["imp_inv_analisis"] = analisis
                    st.session_state.pop("imp_inv_error", None)
                    st.session_state.pop("imp_inv_confirmar", None)
            st.rerun()

    error_archivo = st.session_state.get("imp_inv_error")
    if error_archivo:
        st.error(str(error_archivo))
        if st.button("Reintentar lectura", key="imp_inv_reintentar"):
            st.session_state.pop("imp_inv_error", None)
            st.session_state.pop("imp_inv_firma", None)
            st.rerun()
        return

    if not guardado:
        st.caption(
            "Descarga la plantilla, completa la hoja de movimientos y súbela "
            "aquí. También puedes usar la hoja «Movimientos_Registrados_App». "
            "La vista previa se genera automáticamente al cargar el archivo."
        )
        return

    analisis = st.session_state.get("imp_inv_analisis")
    if not analisis:
        return

    _render_preview(
        user,
        guardado.get("contenido") or b"",
        str(guardado.get("nombre") or "movimientos_inventario.xlsx"),
        analisis,
    )
