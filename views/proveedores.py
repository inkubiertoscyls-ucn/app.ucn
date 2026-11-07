"""Administración del catálogo de proveedores de INKubiertos.

Permite listar, buscar, filtrar, registrar, editar y activar/desactivar
proveedores. El RUT es la clave primaria real y no se puede modificar después
del alta para no romper las referencias de inventario.
"""
from __future__ import annotations

import unicodedata
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from core.utils import formatear_rut
from data.errors import ErrorDatos
from data.permisos import ADMINISTRADOR
from data.proveedores import (
    cambiar_estado_proveedor,
    listar_proveedores_admin,
    modificar_proveedor,
    registrar_proveedor,
)
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.layout import metric_grid, page_header, status_badge
from ui.state import flash, render_flash

TODOS = "Todos"
SIN_TIPO = "Sin tipo"
ESTADOS = [TODOS, "Activos", "Inactivos"]


def _normalizar(texto: Any) -> str:
    """Minúsculas, sin tildes y sin espacios sobrantes."""
    valor = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(
        caracter for caracter in valor if not unicodedata.combining(caracter)
    ).strip().casefold()


def _tipo(fila: Dict[str, Any]) -> str:
    return str(fila.get("tipo_proveedor") or "").strip() or SIN_TIPO


def _orden(fila: Dict[str, Any]) -> tuple:
    return (
        0 if fila.get("activo") else 1,
        str(fila.get("nombre_proveedor") or "").casefold(),
    )


def _tipos(proveedores: List[Dict[str, Any]]) -> List[str]:
    return sorted(
        {_tipo(fila) for fila in proveedores},
        key=lambda valor: (valor.casefold(), valor),
    )


def filtrar_proveedores(
    proveedores: List[Dict[str, Any]],
    *,
    texto: str = "",
    tipo: str = TODOS,
    estado: str = TODOS,
) -> List[Dict[str, Any]]:
    """Aplica búsqueda por nombre/RUT/contacto/tipo y filtros de catálogo."""
    termino = _normalizar(texto)
    tipo_normalizado = _normalizar(tipo)
    resultado = []

    for fila in proveedores:
        if tipo != TODOS and _normalizar(_tipo(fila)) != tipo_normalizado:
            continue
        if estado == "Activos" and not fila.get("activo"):
            continue
        if estado == "Inactivos" and fila.get("activo"):
            continue
        if termino:
            campos = (
                _normalizar(fila.get("nombre_proveedor")),
                _normalizar(fila.get("rut_proveedor")),
                _normalizar(formatear_rut(fila.get("rut_proveedor"))),
                _normalizar(fila.get("contacto_proveedor")),
                _normalizar(_tipo(fila)),
            )
            if not any(termino in campo for campo in campos):
                continue
        resultado.append(fila)

    return sorted(resultado, key=_orden)


def _metricas(proveedores: List[Dict[str, Any]]) -> None:
    total = len(proveedores)
    activos = sum(1 for fila in proveedores if fila.get("activo"))
    inactivos = total - activos
    tipos = len({_tipo(fila) for fila in proveedores} - {SIN_TIPO})

    metric_grid(
        [
            {
                "label": "Proveedores",
                "value": total,
                "hint": "Registros del catálogo, activos e inactivos.",
                "tone": "default",
            },
            {
                "label": "Activos",
                "value": activos,
                "hint": "Disponibles en los movimientos de Inventario.",
                "tone": "green",
            },
            {
                "label": "Inactivos",
                "value": inactivos,
                "hint": "Ocultos para nuevas operaciones, con historial intacto.",
                "tone": "amber",
            },
            {
                "label": "Tipos",
                "value": tipos,
                "hint": "Tipos distintos con al menos un proveedor.",
                "tone": "wine",
            },
        ]
    )


def _tabla_proveedores(proveedores: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in proveedores:
        activo = bool(fila.get("activo"))
        estado = status_badge(
            "Activo" if activo else "Inactivo", "green" if activo else "muted"
        )
        rut = str(fila.get("rut_proveedor") or "")
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("nombre_proveedor") or "Sin nombre"))}</span></td>'
            f"<td>{escape(formatear_rut(rut) if rut else '—')}</td>"
            f"<td>{escape(str(fila.get('contacto_proveedor') or '—'))}</td>"
            f"<td>{escape(_tipo(fila))}</td>"
            f"<td>{estado}</td>"
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Proveedor</th><th>RUT</th><th>Contacto</th>"
        "<th>Tipo</th><th>Estado</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _formulario_proveedor(
    proveedor: Optional[Dict[str, Any]],
    usuario: Dict[str, Any],
    *,
    editar: bool,
) -> None:
    identificador = str(proveedor.get("rut_proveedor")) if proveedor else "nuevo"
    clave = f"prov_form_{'editar' if editar else 'nuevo'}_{identificador}"

    with st.form(key=clave, clear_on_submit=not editar):
        col_izquierda, col_derecha = st.columns(2, gap="large")
        with col_izquierda:
            rut = st.text_input(
                "RUT del proveedor",
                value=(
                    formatear_rut(str(proveedor.get("rut_proveedor") or ""))
                    if proveedor
                    else ""
                ),
                max_chars=12,
                key=f"{clave}_rut",
                help=(
                    "Obligatorio y único. Se guarda sin puntos ni guion."
                    if not editar
                    else "El RUT no se puede modificar después del alta."
                ),
                disabled=editar,
            )
            nombre = st.text_input(
                "Nombre del proveedor",
                value=str(proveedor.get("nombre_proveedor") or "") if proveedor else "",
                max_chars=150,
                key=f"{clave}_nombre",
                help="Obligatorio, entre 2 y 150 caracteres.",
            )
        with col_derecha:
            contacto = st.text_input(
                "Contacto",
                value=str(proveedor.get("contacto_proveedor") or "") if proveedor else "",
                max_chars=150,
                key=f"{clave}_contacto",
                help="Opcional. Nombre, teléfono o correo de contacto.",
            )
            tipo = st.text_input(
                "Tipo de proveedor",
                value=str(proveedor.get("tipo_proveedor") or "") if proveedor else "",
                max_chars=100,
                key=f"{clave}_tipo",
                help="Opcional. Ejemplos: Insumos, Bebidas, Verduras.",
            )

        if editar:
            st.caption(
                "El RUT identifica al proveedor en los movimientos de Inventario "
                "y no se puede cambiar."
            )

        enviado = st.form_submit_button(
            "Guardar cambios" if editar else "Registrar proveedor",
            type="primary",
            use_container_width=True,
        )

    if not enviado:
        return

    datos = {
        "nombre_proveedor": nombre,
        "contacto_proveedor": contacto,
        "tipo_proveedor": tipo,
    }
    if not editar:
        datos["rut_proveedor"] = rut

    try:
        with cargando("Guardando proveedor…"):
            if editar and proveedor:
                modificar_proveedor(
                    str(proveedor["rut_proveedor"]), datos, usuario=usuario
                )
                mensaje = f"El proveedor «{nombre.strip()}» quedó actualizado."
            else:
                registrar_proveedor(datos, usuario=usuario)
                mensaje = f"El proveedor «{nombre.strip()}» quedó registrado."
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo guardar el proveedor.")
        return
    except Exception:
        st.error("No se pudo guardar el proveedor. Intenta nuevamente.")
        return

    flash("success", mensaje)
    st.rerun()


def _panel_edicion(
    proveedores: List[Dict[str, Any]], usuario: Dict[str, Any]
) -> None:
    seleccionado = st.selectbox(
        "Proveedor a editar",
        proveedores,
        format_func=lambda fila: (
            f"{fila.get('nombre_proveedor') or 'Sin nombre'} · "
            f"{formatear_rut(str(fila.get('rut_proveedor') or ''))} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="prov_editar_proveedor",
    )
    if not seleccionado:
        return
    _formulario_proveedor(seleccionado, usuario, editar=True)


def _panel_estado(
    proveedores: List[Dict[str, Any]], usuario: Dict[str, Any]
) -> None:
    st.caption(
        "Activar o desactivar no elimina el proveedor ni su historial de "
        "movimientos. Un proveedor inactivo deja de aparecer en los selectores "
        "de Inventario."
    )
    seleccionado = st.selectbox(
        "Proveedor",
        proveedores,
        format_func=lambda fila: (
            f"{fila.get('nombre_proveedor') or 'Sin nombre'} · "
            f"{formatear_rut(str(fila.get('rut_proveedor') or ''))} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="prov_estado_proveedor",
    )
    if not seleccionado:
        return

    rut = str(seleccionado["rut_proveedor"])
    nombre = str(seleccionado.get("nombre_proveedor") or "el proveedor")
    activo = bool(seleccionado.get("activo"))
    accion = "desactivar" if activo else "activar"

    confirmar = st.checkbox(
        f"Confirmo que quiero {accion} «{nombre}».",
        key=f"prov_confirmar_{accion}_{rut}",
    )
    if st.button(
        "Desactivar proveedor" if activo else "Activar proveedor",
        key=f"prov_boton_{accion}_{rut}",
        type="primary",
        disabled=not confirmar,
        use_container_width=True,
    ):
        try:
            with cargando(f"Procesando «{nombre}»…"):
                cambiar_estado_proveedor(rut, not activo, usuario=usuario)
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo=f"No se pudo {accion} el proveedor.")
            return
        except Exception:
            st.error(f"No se pudo {accion} el proveedor. Intenta nuevamente.")
            return

        flash(
            "success",
            f"El proveedor «{nombre}» quedó {'activo' if not activo else 'inactivo'}.",
        )
        st.rerun()


def render_proveedores() -> None:
    """Renderiza la administración de proveedores para un administrador."""
    usuario = st.session_state.get("user") or {}
    if usuario.get("rol") != ADMINISTRADOR:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

    page_header("Proveedores", "Administración del catálogo de proveedores")
    render_flash()
    st.markdown(
        '<div class="ink-scope">Administración · catálogo de proveedores</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "El RUT es la clave del proveedor y no se modifica después del alta. "
        "Desactivar conserva el historial de inventario."
    )

    try:
        with cargando("Cargando proveedores…"):
            proveedores = listar_proveedores_admin(usuario=usuario)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar los proveedores.")
        boton_reintentar("proveedores")
        return

    proveedores = sorted(proveedores, key=_orden)

    if proveedores:
        _metricas(proveedores)

        col_buscar, col_tipo, col_estado = st.columns(
            [2.2, 1.3, 1.2], gap="medium"
        )
        with col_buscar:
            texto = st.text_input(
                "Buscar proveedor",
                placeholder="Nombre, RUT, contacto o tipo",
                key="prov_buscar",
            )
        with col_tipo:
            tipo = st.selectbox(
                "Tipo de proveedor",
                [TODOS] + _tipos(proveedores),
                key="prov_tipo",
            )
        with col_estado:
            estado = st.selectbox("Estado", ESTADOS, key="prov_estado")

        filtrados = filtrar_proveedores(
            proveedores,
            texto=texto,
            tipo=tipo,
            estado=estado,
        )

        st.markdown(
            '<div class="ink-table-meta">'
            f"<span>{len(filtrados)} de {len(proveedores)} proveedores</span>"
            "<span>El RUT no se puede editar</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        if filtrados:
            st.markdown(_tabla_proveedores(filtrados), unsafe_allow_html=True)
        else:
            mostrar_vacio(
                "No hay proveedores que coincidan con la búsqueda o los filtros "
                "seleccionados. Prueba con otro término o restablece los filtros."
            )
            if st.button("Limpiar filtros", key="prov_limpiar", type="secondary"):
                for clave in ("prov_buscar", "prov_tipo", "prov_estado"):
                    st.session_state.pop(clave, None)
                st.rerun()
    else:
        mostrar_vacio(
            "Aún no hay proveedores registrados. Crea el primero con el "
            "formulario de abajo; aparecerá en los movimientos de Inventario "
            "cuando registres una entrada real."
        )

    st.markdown("---")
    st.markdown("**Registrar proveedor**")
    with st.expander(
        "Datos del nuevo proveedor",
        expanded=not proveedores,
    ):
        _formulario_proveedor(None, usuario, editar=False)

    if proveedores:
        st.markdown("**Editar proveedor**")
        with st.expander("Selecciona un proveedor y actualiza sus datos", expanded=False):
            _panel_edicion(proveedores, usuario)

        st.markdown("**Activar o desactivar proveedor**")
        with st.expander("Cambiar el estado del proveedor", expanded=False):
            _panel_estado(proveedores, usuario)
