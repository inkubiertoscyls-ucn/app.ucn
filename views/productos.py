"""Administración del catálogo de productos de INKubiertos.

Permite listar, buscar, filtrar, registrar, editar y activar/desactivar
productos. El stock no se almacena ni se modifica desde esta pantalla: se
calcula desde los movimientos de inventario.
"""
from __future__ import annotations

import unicodedata
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.permisos import ADMINISTRADOR
from data.productos import (
    cambiar_estado_producto,
    listar_productos_admin,
    modificar_producto,
    registrar_producto,
)
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_cantidad, fmt_clp
from ui.layout import metric_grid, page_header, status_badge
from ui.state import flash, render_flash

TODOS = "Todos"
TODAS = "Todas"
SIN_CATEGORIA = "Sin categoría"
ESTADOS = [TODOS, "Activos", "Inactivos"]


def _normalizar(texto: Any) -> str:
    """Minúsculas, sin tildes y sin espacios sobrantes."""
    valor = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(
        caracter for caracter in valor if not unicodedata.combining(caracter)
    ).strip().casefold()


def _categoria(fila: Dict[str, Any]) -> str:
    return str(fila.get("categoria") or "").strip() or SIN_CATEGORIA


def _orden(fila: Dict[str, Any]) -> tuple:
    return (
        0 if fila.get("activo") else 1,
        str(fila.get("nombre_producto") or "").casefold(),
    )


def _categorias(productos: List[Dict[str, Any]]) -> List[str]:
    return sorted(
        {_categoria(fila) for fila in productos},
        key=lambda valor: (valor.casefold(), valor),
    )


def filtrar_productos(
    productos: List[Dict[str, Any]],
    *,
    texto: str = "",
    categoria: str = TODAS,
    estado: str = TODOS,
) -> List[Dict[str, Any]]:
    """Aplica búsqueda por nombre/categoría/unidad y filtros de catálogo."""
    termino = _normalizar(texto)
    categoria_normalizada = _normalizar(categoria)
    resultado = []

    for fila in productos:
        if categoria != TODAS and _normalizar(_categoria(fila)) != categoria_normalizada:
            continue
        if estado == "Activos" and not fila.get("activo"):
            continue
        if estado == "Inactivos" and fila.get("activo"):
            continue
        if termino:
            campos = (
                _normalizar(fila.get("nombre_producto")),
                _normalizar(_categoria(fila)),
                _normalizar(fila.get("unidad_medida")),
            )
            if not any(termino in campo for campo in campos):
                continue
        resultado.append(fila)

    return sorted(resultado, key=_orden)


def _numero(valor: Any) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _metricas(productos: List[Dict[str, Any]]) -> None:
    total = len(productos)
    activos = sum(1 for fila in productos if fila.get("activo"))
    inactivos = total - activos
    categorias = len({_categoria(fila) for fila in productos} - {SIN_CATEGORIA})

    metric_grid(
        [
            {
                "label": "Productos",
                "value": total,
                "hint": "Registros del catálogo, activos e inactivos.",
                "tone": "default",
            },
            {
                "label": "Activos",
                "value": activos,
                "hint": "Disponibles en Inventario y Movimientos.",
                "tone": "green",
            },
            {
                "label": "Inactivos",
                "value": inactivos,
                "hint": "Ocultos para nuevas operaciones, con historial intacto.",
                "tone": "amber",
            },
            {
                "label": "Categorías",
                "value": categorias,
                "hint": "Categorías distintas con al menos un producto.",
                "tone": "wine",
            },
        ]
    )


def _tabla_productos(productos: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for fila in productos:
        activo = bool(fila.get("activo"))
        estado = status_badge("Activo" if activo else "Inactivo", "green" if activo else "muted")
        costo = fila.get("costo_base")
        costo_texto = "—" if costo is None else fmt_clp(costo)
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("nombre_producto") or "Sin nombre"))}</span></td>'
            f"<td>{escape(_categoria(fila))}</td>"
            f"<td>{escape(str(fila.get('unidad_medida') or '—'))}</td>"
            f'<td class="is-num">{escape(costo_texto)}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("stock_minimo")))}</td>'
            f'<td class="is-num">{escape(fmt_cantidad(fila.get("stock_maximo")))}</td>'
            f"<td>{estado}</td>"
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Producto</th><th>Categoría</th><th>Unidad</th>"
        "<th class='is-num'>Costo base</th>"
        "<th class='is-num'>Stock mínimo</th><th class='is-num'>Stock máximo</th>"
        "<th>Estado</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _formulario_producto(
    producto: Optional[Dict[str, Any]],
    usuario: Dict[str, Any],
    *,
    editar: bool,
) -> None:
    identificador = int(producto["id_producto"]) if producto else "nuevo"
    clave = f"prod_form_{'editar' if editar else 'nuevo'}_{identificador}"

    with st.form(key=clave, clear_on_submit=not editar):
        col_izquierda, col_derecha = st.columns(2, gap="large")
        with col_izquierda:
            nombre = st.text_input(
                "Nombre del producto",
                value=str(producto.get("nombre_producto") or "") if producto else "",
                max_chars=150,
                key=f"{clave}_nombre",
                help="Obligatorio, entre 2 y 150 caracteres.",
            )
            categoria = st.text_input(
                "Categoría",
                value=str(producto.get("categoria") or "") if producto else "",
                max_chars=100,
                key=f"{clave}_categoria",
                help="Opcional. Se usa para filtrar y agrupar.",
            )
            unidad = st.text_input(
                "Unidad de medida",
                value=str(producto.get("unidad_medida") or "") if producto else "",
                max_chars=50,
                key=f"{clave}_unidad",
                help="Obligatoria. Opciones permitidas: Unidad, Botella, kg, L (respetar mayúsculas y minúsculas).",
            )
        with col_derecha:
            costo = st.number_input(
                "Costo base (CLP)",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=_numero(producto.get("costo_base")) if producto else 0.0,
                key=f"{clave}_costo",
                help="Costo estimado por unidad. No modifica ventas históricas.",
            )
            minimo = st.number_input(
                "Stock mínimo",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                value=_numero(producto.get("stock_minimo")) if producto else 0.0,
                key=f"{clave}_minimo",
                help="Umbral para las alertas de stock.",
            )
            maximo = st.number_input(
                "Stock máximo",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                value=_numero(producto.get("stock_maximo")) if producto else 0.0,
                key=f"{clave}_maximo",
                help="0 significa sin máximo configurado.",
            )

        if editar:
            st.caption(
                "El stock actual no se edita aquí: se calcula desde los movimientos "
                "de Inventario."
            )

        enviado = st.form_submit_button(
            "Guardar cambios" if editar else "Registrar producto",
            type="primary",
            use_container_width=True,
        )

    if not enviado:
        return

    datos = {
        "nombre_producto": nombre,
        "categoria": categoria,
        "unidad_medida": unidad,
        "costo_base": costo,
        "stock_minimo": minimo,
        "stock_maximo": maximo,
    }

    try:
        with cargando("Guardando producto…"):
            if editar and producto:
                modificar_producto(
                    int(producto["id_producto"]), datos, usuario=usuario
                )
                mensaje = f"El producto «{nombre.strip()}» quedó actualizado."
            else:
                registrar_producto(datos, usuario=usuario)
                mensaje = f"El producto «{nombre.strip()}» quedó registrado."
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo guardar el producto.")
        return
    except Exception:
        st.error("No se pudo guardar el producto. Intenta nuevamente.")
        return

    flash("success", mensaje)
    st.rerun()


def _panel_edicion(productos: List[Dict[str, Any]], usuario: Dict[str, Any]) -> None:
    seleccionado = st.selectbox(
        "Producto a editar",
        productos,
        format_func=lambda fila: (
            f"{fila.get('nombre_producto') or 'Sin nombre'} · "
            f"{_categoria(fila)} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="prod_editar_producto",
    )
    if not seleccionado:
        return
    _formulario_producto(seleccionado, usuario, editar=True)


def _panel_estado(productos: List[Dict[str, Any]], usuario: Dict[str, Any]) -> None:
    st.caption(
        "Activar o desactivar no elimina el producto ni su historial de "
        "movimientos. Un producto inactivo deja de aparecer en Inventario y en "
        "los selectores de Movimientos."
    )
    seleccionado = st.selectbox(
        "Producto",
        productos,
        format_func=lambda fila: (
            f"{fila.get('nombre_producto') or 'Sin nombre'} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="prod_estado_producto",
    )
    if not seleccionado:
        return

    identificador = int(seleccionado["id_producto"])
    nombre = str(seleccionado.get("nombre_producto") or "el producto")
    activo = bool(seleccionado.get("activo"))
    accion = "desactivar" if activo else "activar"

    confirmar = st.checkbox(
        f"Confirmo que quiero {accion} «{nombre}».",
        key=f"prod_confirmar_{accion}_{identificador}",
    )
    if st.button(
        "Desactivar producto" if activo else "Activar producto",
        key=f"prod_boton_{accion}_{identificador}",
        type="primary",
        disabled=not confirmar,
        use_container_width=True,
    ):
        try:
            with cargando(f"Procesando «{nombre}»…"):
                cambiar_estado_producto(
                    identificador, not activo, usuario=usuario
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo=f"No se pudo {accion} el producto.")
            return
        except Exception:
            st.error(f"No se pudo {accion} el producto. Intenta nuevamente.")
            return

        flash(
            "success",
            f"El producto «{nombre}» quedó {'activo' if not activo else 'inactivo'}.",
        )
        st.rerun()


def render_productos() -> None:
    """Renderiza la administración del catálogo para un administrador."""
    usuario = st.session_state.get("user") or {}
    if usuario.get("rol") != ADMINISTRADOR:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

    page_header("Productos", "Administración del catálogo de productos")
    render_flash()
    st.markdown(
        '<div class="ink-scope">Administración · catálogo de productos</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "El catálogo es global. El stock se calcula desde los movimientos de "
        "Inventario y no se crea al registrar un producto."
    )

    try:
        with cargando("Cargando productos…"):
            productos = listar_productos_admin(usuario=usuario)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar los productos.")
        boton_reintentar("productos")
        return

    productos = sorted(productos, key=_orden)

    if productos:
        _metricas(productos)

        col_buscar, col_categoria, col_estado = st.columns(
            [2.2, 1.3, 1.2], gap="medium"
        )
        with col_buscar:
            texto = st.text_input(
                "Buscar producto",
                placeholder="Nombre, categoría o unidad",
                key="prod_buscar",
            )
        with col_categoria:
            categoria = st.selectbox(
                "Categoría",
                [TODAS] + _categorias(productos),
                key="prod_categoria",
            )
        with col_estado:
            estado = st.selectbox("Estado", ESTADOS, key="prod_estado")

        filtrados = filtrar_productos(
            productos,
            texto=texto,
            categoria=categoria,
            estado=estado,
        )

        st.markdown(
            '<div class="ink-table-meta">'
            f"<span>{len(filtrados)} de {len(productos)} productos</span>"
            "<span>El stock actual se consulta en Inventario</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        if filtrados:
            st.markdown(_tabla_productos(filtrados), unsafe_allow_html=True)
        else:
            mostrar_vacio(
                "No hay productos que coincidan con la búsqueda o los filtros "
                "seleccionados. Prueba con otro término o restablece los filtros."
            )
            if st.button("Limpiar filtros", key="prod_limpiar", type="secondary"):
                for clave in ("prod_buscar", "prod_categoria", "prod_estado"):
                    st.session_state.pop(clave, None)
                st.rerun()
    else:
        mostrar_vacio(
            "Aún no hay productos registrados. Crea el primero con el formulario "
            "de abajo; aparecerá en Inventario con stock 0 hasta que registres "
            "un movimiento real."
        )

    st.markdown("---")
    st.markdown("**Registrar producto**")
    with st.expander(
        "Datos del nuevo producto",
        expanded=not productos,
    ):
        _formulario_producto(None, usuario, editar=False)

    if productos:
        st.markdown("**Editar producto**")
        with st.expander("Selecciona un producto y actualiza sus datos", expanded=False):
            _panel_edicion(productos, usuario)

        st.markdown("**Activar o desactivar producto**")
        with st.expander("Cambiar el estado del producto", expanded=False):
            _panel_estado(productos, usuario)
