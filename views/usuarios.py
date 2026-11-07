"""Administración de usuarios de INKubiertos.

Permite al administrador consultar las cuentas registradas, buscar y filtrar,
y activar o desactivar operarios sin borrar su historial. La contraseña y su
hash nunca se incluyen en las filas que llegan a esta pantalla.
"""
from __future__ import annotations

import unicodedata
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.permisos import ADMINISTRADOR
from data.usuarios import activar_usuario, desactivar_usuario, listar_usuarios
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_fecha, resolver_area
from ui.layout import metric_grid, page_header, status_badge
from ui.state import flash, render_flash

TODOS = "Todos"
TODAS_LAS_AREAS = "Todas las áreas"
ROLES = [TODOS, "Administrador", "Operario"]
ESTADOS = [TODOS, "Activos", "Inactivos"]


def _normalizar(texto: Any) -> str:
    """Minúsculas, sin acentos y con espacios simples."""
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", str(texto or ""))
        if not unicodedata.combining(caracter)
    )
    return " ".join(sin_acentos.casefold().split())


def _clave_busqueda(texto: Any) -> str:
    """Clave para buscar nombres y RUT sin puntos, guiones ni espacios."""
    return "".join(
        caracter for caracter in _normalizar(texto) if caracter.isalnum()
    )


def _area_texto(valor: Any) -> str:
    """Nombre de área legible para la tabla."""
    nombre = resolver_area(valor)
    if not nombre:
        return "Sin área"
    if nombre.casefold() == "todas":
        return "Todas"
    return nombre


def _orden(fila: Dict[str, Any]) -> tuple:
    """Activos primero, luego administradores, y después por nombre."""
    return (
        0 if fila.get("activo") else 1,
        0 if fila.get("rol") == ADMINISTRADOR else 1,
        _normalizar(fila.get("nombre_usuario")),
        str(fila.get("rut_usuario") or ""),
    )


def filtrar_usuarios(
    filas: List[Dict[str, Any]],
    *,
    texto: str = "",
    rol: Optional[str] = None,
    estado: Optional[str] = None,
    area: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aplica búsqueda y filtros sobre las filas ya autorizadas.

    Se ejecuta en memoria después de que la capa de datos validó el rol, de
    modo que ningún filtro pueda ampliar el acceso del usuario.
    """
    termino = _clave_busqueda(texto)
    rol_filtro = _normalizar(rol)
    estado_filtro = _normalizar(estado)
    area_filtro = _normalizar(area)
    sin_rol = rol_filtro in {"", "todos", "todas"}
    sin_area = area_filtro in {"", "todas las areas"}

    resultado: List[Dict[str, Any]] = []
    for fila in filas:
        nombre = str(fila.get("nombre_usuario") or "")
        rut = str(fila.get("rut_usuario") or "")

        if termino and (
            termino not in _clave_busqueda(nombre)
            and termino not in _clave_busqueda(rut)
        ):
            continue
        if not sin_rol and _normalizar(fila.get("rol")) != rol_filtro:
            continue

        activo = bool(fila.get("activo"))
        if estado_filtro in {"activos", "activo"} and not activo:
            continue
        if estado_filtro in {"inactivos", "inactivo"} and activo:
            continue

        if (
            not sin_area
            and _normalizar(_area_texto(fila.get("area_asignada"))) != area_filtro
        ):
            continue

        resultado.append(fila)

    resultado.sort(key=_orden)
    return resultado


def _tabla_usuarios(
    filas: List[Dict[str, Any]],
    *,
    actual_rut: str = "",
) -> str:
    """Tabla HTML sin datos sensibles."""
    cuerpo = []
    for fila in filas:
        rut = str(fila.get("rut_usuario") or "")
        nombre = escape(str(fila.get("nombre_usuario") or "Sin nombre"))
        if rut and rut == actual_rut:
            nombre += ' <span class="ink-muted">(tú)</span>'

        activo = bool(fila.get("activo"))
        estado = (
            status_badge("Activo", "green")
            if activo
            else status_badge("Inactivo", "amber")
        )
        rol = escape(str(fila.get("rol") or "—"))

        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">{nombre}</span></td>'
            f'<td class="is-num">{escape(rut or "—")}</td>'
            f"<td>{rol}</td>"
            f"<td>{escape(_area_texto(fila.get('area_asignada')))}</td>"
            f"<td>{estado}</td>"
            f'<td class="is-date">{escape(fmt_fecha(fila.get("fecha_creacion")))}</td>'
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr><th>Usuario</th><th class='is-num'>RUT</th>"
        "<th>Rol</th><th>Área asignada</th><th>Estado</th>"
        "<th>Fecha de creación</th></tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _metricas(usuarios: List[Dict[str, Any]]) -> None:
    total = len(usuarios)
    activos = sum(1 for usuario in usuarios if usuario.get("activo"))
    inactivos = total - activos
    administradores = sum(
        1 for usuario in usuarios if usuario.get("rol") == ADMINISTRADOR
    )
    metric_grid(
        [
            {
                "label": "Usuarios",
                "value": total,
                "hint": "Cuentas registradas en el sistema.",
                "tone": "default",
            },
            {
                "label": "Activos",
                "value": activos,
                "hint": "Pueden iniciar sesión.",
                "tone": "green",
            },
            {
                "label": "Inactivos",
                "value": inactivos,
                "hint": "Pendientes de activación o deshabilitados.",
                "tone": "amber",
            },
            {
                "label": "Administradores",
                "value": administradores,
                "hint": "Incluye cuentas activas e inactivas.",
                "tone": "wine",
            },
        ]
    )


def _ejecutar_cambio(
    *,
    activar: bool,
    rut: str,
    nombre: str,
    usuario: Dict[str, Any],
) -> None:
    """Ejecuta la activación o desactivación y deja un mensaje para el rerun."""
    accion = "activar" if activar else "desactivar"
    try:
        with cargando(f"Procesando la cuenta de {nombre}…"):
            if activar:
                activar_usuario(rut, usuario=usuario)
            else:
                desactivar_usuario(rut, usuario=usuario)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo=f"No se pudo {accion} la cuenta.")
        return
    except Exception:
        st.error(
            f"No se pudo {accion} la cuenta. Intenta nuevamente en unos minutos."
        )
        return

    flash(
        "success",
        f"La cuenta de {nombre} quedó {'activa' if activar else 'inactiva'}.",
    )
    st.rerun()


def _panel_estado(
    usuarios: List[Dict[str, Any]],
    usuario: Dict[str, Any],
) -> None:
    """Panel para activar o desactivar una cuenta con confirmación."""
    st.markdown("---")
    st.markdown("**Activar o desactivar una cuenta**")
    st.caption(
        "El cambio solo modifica el estado de la cuenta. No elimina al usuario, "
        "su área ni los movimientos o registros asociados a su historial."
    )

    if not usuarios:
        return

    actual_rut = str(usuario.get("rut_usuario") or "")
    indice_inicial = next(
        (
            indice
            for indice, fila in enumerate(usuarios)
            if not fila.get("activo")
        ),
        0,
    )
    seleccionado = st.selectbox(
        "Usuario",
        usuarios,
        index=indice_inicial,
        format_func=lambda fila: (
            f"{fila.get('nombre_usuario') or 'Sin nombre'} · "
            f"{fila.get('rut_usuario') or '—'} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="usr_estado_usuario",
    )
    if not seleccionado:
        return

    rut = str(seleccionado.get("rut_usuario") or "")
    nombre = str(seleccionado.get("nombre_usuario") or "la cuenta")
    activo = bool(seleccionado.get("activo"))

    if activo:
        if rut == actual_rut:
            st.info(
                "No puedes desactivar tu propia cuenta. Si necesitas dejar de "
                "usar el sistema, otro administrador debe desactivarla."
            )
            return

        if seleccionado.get("rol") == ADMINISTRADOR:
            administradores_activos = [
                fila
                for fila in usuarios
                if fila.get("rol") == ADMINISTRADOR and fila.get("activo")
            ]
            if len(administradores_activos) <= 1:
                st.warning(
                    "Esta es la única cuenta de administrador activa. El sistema "
                    "debe conservar al menos una para poder administrarse."
                )
                return

        confirmar = st.checkbox(
            f"Confirmo que quiero desactivar la cuenta de {nombre}.",
            key=f"usr_confirmar_desactivar_{rut}",
        )
        if st.button(
            "Desactivar cuenta",
            key="usr_desactivar",
            type="primary",
            disabled=not confirmar,
            use_container_width=True,
        ):
            _ejecutar_cambio(
                activar=False,
                rut=rut,
                nombre=nombre,
                usuario=usuario,
            )
        return

    confirmar = st.checkbox(
        f"Confirmo que quiero activar la cuenta de {nombre}.",
        key=f"usr_confirmar_activar_{rut}",
    )
    if st.button(
        "Activar cuenta",
        key="usr_activar",
        type="primary",
        disabled=not confirmar,
        use_container_width=True,
    ):
        _ejecutar_cambio(
            activar=True,
            rut=rut,
            nombre=nombre,
            usuario=usuario,
        )


def render_usuarios() -> None:
    """Renderiza la administración de usuarios para un administrador."""
    usuario = st.session_state.get("user") or {}
    if usuario.get("rol") != ADMINISTRADOR:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

    page_header("Usuarios", "Administración de cuentas y accesos")
    render_flash()
    st.markdown(
        '<div class="ink-scope">Administración · cuentas del sistema</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Los operarios se registran desde el inicio de sesión y quedan "
        "inactivos hasta que un administrador active su cuenta."
    )

    try:
        with cargando("Cargando usuarios…"):
            usuarios = listar_usuarios(usuario=usuario)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar los usuarios.")
        boton_reintentar("usuarios")
        return

    if not usuarios:
        mostrar_vacio(
            "Aún no hay usuarios registrados. Las cuentas de operario aparecerán "
            "aquí después de registrarse desde el inicio de sesión."
        )
        return

    usuarios = sorted(usuarios, key=_orden)
    # Se dibuja fuera del try de datos: un fallo de renderizado no debe
    # presentarse como un error de conexión a Supabase.
    _metricas(usuarios)

    col_buscar, col_rol, col_estado, col_area = st.columns(
        [2.2, 1.1, 1.1, 1.3], gap="medium"
    )
    with col_buscar:
        texto = st.text_input(
            "Buscar usuario",
            placeholder="Nombre o RUT",
            key="usr_buscar",
        )
    with col_rol:
        rol = st.selectbox("Rol", ROLES, key="usr_rol")
    with col_estado:
        estado = st.selectbox("Estado", ESTADOS, key="usr_estado")
    with col_area:
        areas = sorted(
            {_area_texto(fila.get("area_asignada")) for fila in usuarios},
            key=lambda valor: (valor.casefold(), valor),
        )
        opciones_area = [TODAS_LAS_AREAS] + [
            nombre for nombre in areas if nombre != TODAS_LAS_AREAS
        ]
        area = st.selectbox("Área", opciones_area, key="usr_area")

    filtradas = filtrar_usuarios(
        usuarios,
        texto=texto,
        rol=rol,
        estado=estado,
        area=area,
    )

    st.markdown(
        '<div class="ink-table-meta">'
        f"<span>{len(filtradas)} de {len(usuarios)} usuarios</span>"
        "<span>Sin contraseñas ni datos sensibles</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not filtradas:
        mostrar_vacio(
            "No hay usuarios que coincidan con la búsqueda o los filtros "
            "seleccionados. Prueba con otro término o restablece los filtros."
        )
        if st.button("Limpiar filtros", key="usr_limpiar", type="secondary"):
            for clave in ("usr_buscar", "usr_rol", "usr_estado", "usr_area"):
                st.session_state.pop(clave, None)
            st.rerun()
        return

    st.markdown(
        _tabla_usuarios(
            filtradas,
            actual_rut=str(usuario.get("rut_usuario") or ""),
        ),
        unsafe_allow_html=True,
    )

    _panel_estado(usuarios, usuario)
