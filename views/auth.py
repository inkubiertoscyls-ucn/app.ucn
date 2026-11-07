"""Pantallas de autenticación: login, registro de operarios y aviso de acceso."""
from __future__ import annotations

import streamlit as st

from components.auth import login_form
from core.exceptions import AuthorizationError, ValidationError
from data.catalogos import listar_areas
from data.errors import ErrorDatos
from services.usuarios import UsuariosService
from ui.feedback import cargando, mostrar_error
from ui.state import flash, render_flash

BRAND_PANEL = """
<div class="ink-login-brand">
    <div>
        <div class="ink-login-wordmark">INKubiertos</div>
        <div class="ink-login-tagline">Gestión de inventario y rentabilidad</div>
    </div>
    <div>
        <div class="ink-login-brand-rule"></div>
        <div class="ink-login-brand-copy">
            Existencias, movimientos y alertas del restaurante en un solo lugar.
        </div>
        <div class="ink-login-brand-foot">Acceso exclusivo para usuarios autorizados.</div>
    </div>
</div>
"""


def render_auth() -> None:
    """Renderiza la vista de autenticación activa."""
    st.markdown('<div class="ink-login-wrap"></div>', unsafe_allow_html=True)
    render_flash()

    view = st.session_state.get("auth_view", "login")
    if view == "register":
        _render_register()
    elif view == "forgot":
        _render_forgot()
    else:
        _render_login()


def _render_login() -> None:
    left, right = st.columns([5, 7], gap="large", vertical_alignment="center")

    with left:
        st.markdown(BRAND_PANEL, unsafe_allow_html=True)

    with right:
        st.markdown(
            """
            <div class="ink-login-panel">
                <div class="ink-login-title">Iniciar sesión</div>
                <div class="ink-login-subtitle">
                    Ingresa con tu RUT y contraseña para acceder al sistema.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        login_form()
        st.markdown('<div class="ink-login-divider">o</div>', unsafe_allow_html=True)
        if st.button(
            "Crear cuenta de operario",
            key="go_register",
            type="tertiary",
            use_container_width=True,
        ):
            st.session_state.auth_view = "register"
            st.rerun()
        if st.button(
            "Olvidé mi contraseña",
            key="go_forgot",
            type="tertiary",
            use_container_width=True,
        ):
            st.session_state.auth_view = "forgot"
            st.rerun()
        st.markdown(
            '<div class="ink-login-alt">Las cuentas nuevas quedan pendientes de activación.</div>',
            unsafe_allow_html=True,
        )


def _render_register() -> None:
    if st.button("← Volver a iniciar sesión", key="back_login", type="tertiary"):
        st.session_state.auth_view = "login"
        st.rerun()

    error_areas = None
    try:
        with cargando("Cargando áreas disponibles…"):
            areas = _cargar_areas()
    except ErrorDatos as exc:
        areas = []
        error_areas = exc

    left, right = st.columns([5, 7], gap="large", vertical_alignment="top")

    with left:
        st.markdown(BRAND_PANEL, unsafe_allow_html=True)

    with right:
        st.markdown(
            """
            <div class="ink-login-panel">
                <div class="ink-login-title">Crear cuenta</div>
                <div class="ink-login-subtitle">
                    Completa los datos del operario. Un administrador deberá activar la cuenta.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("register_form", clear_on_submit=False):
            nombre = st.text_input(
                "Nombre completo",
                placeholder="Ej: Juan Pérez",
                key="reg_nombre",
            )
            rut = st.text_input(
                "RUT",
                placeholder="Ej: 12.345.678-5",
                key="reg_rut",
                autocomplete="username",
            )
            area = st.selectbox(
                "Área asignada",
                options=["Seleccionar área"] + [a["nombre_area"] for a in areas],
                key="reg_area",
            )
            st.text_input(
                "Rol",
                value="Operario",
                disabled=True,
                key="reg_rol",
                help="Solo un administrador puede crear cuentas con rol Administrador.",
            )
            password = st.text_input(
                "Contraseña",
                type="password",
                placeholder="Mínimo 8 caracteres",
                key="reg_password",
                autocomplete="new-password",
            )
            confirm = st.text_input(
                "Confirmar contraseña",
                type="password",
                placeholder="Repite la contraseña",
                key="reg_confirm",
                autocomplete="new-password",
            )

            submitted = st.form_submit_button(
                "Crear cuenta",
                type="primary",
                use_container_width=True,
                disabled=not areas,
            )

            if submitted:
                _registrar_operario(nombre, rut, area, password, confirm)

        if error_areas is not None:
            mostrar_error(error_areas, prefijo="No se pudieron cargar las áreas.")
        elif not areas:
            st.warning(
                "No hay áreas disponibles. Un administrador debe revisar el catálogo antes de crear cuentas."
            )

        st.markdown(
            '<div class="ink-auth-note">'
            "La cuenta se crea inactiva. Un administrador debe activarla desde "
            "la sección Usuarios para que puedas ingresar."
            "</div>",
            unsafe_allow_html=True,
        )


def _render_forgot() -> None:
    if st.button("← Volver a iniciar sesión", key="back_login_forgot", type="tertiary"):
        st.session_state.auth_view = "login"
        st.rerun()

    left, right = st.columns([5, 7], gap="large", vertical_alignment="center")

    with left:
        st.markdown(BRAND_PANEL, unsafe_allow_html=True)

    with right:
        st.markdown(
            """
            <div class="ink-login-panel">
                <div class="ink-login-title">Recuperar acceso</div>
                <div class="ink-login-subtitle">
                    La recuperación de contraseña la realiza un administrador.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="ink-auth-note">'
            "Por seguridad, no existe un restablecimiento automático por correo. "
            "Contacta al administrador de INKubiertos para recuperar el acceso "
            "a tu cuenta."
            "</div>",
            unsafe_allow_html=True,
        )


def _cargar_areas() -> list[dict]:
    """Áreas activas desde la capa de datos (con caché y errores claros)."""
    return listar_areas()


def _registrar_operario(
    nombre: str,
    rut: str,
    area: str,
    password: str,
    confirm: str,
) -> None:
    nombre = (nombre or "").strip()
    rut = (rut or "").strip()

    if len(nombre) < 3:
        st.error("Ingresa el nombre completo del operario.")
        return
    if not rut:
        st.error("El RUT es obligatorio.")
        return
    if area == "Seleccionar área":
        st.error("Selecciona el área asignada.")
        return
    if len(password or "") < 8:
        st.error("La contraseña debe tener al menos 8 caracteres.")
        return
    if password != confirm:
        st.error("Las contraseñas no coinciden.")
        return

    data = {
        "rut_usuario": rut,
        "nombre_usuario": nombre,
        "rol": "Operario",
        "area_asignada": area,
        "activo": False,
        "password": password,
    }

    try:
        UsuariosService().registrar_usuario(data)
    except (ValidationError, AuthorizationError) as error:
        st.error(str(error))
        return
    except Exception:
        st.error("No se pudo crear la cuenta. Intenta nuevamente en unos minutos.")
        return

    flash(
        "success",
        "Cuenta creada. Quedó inactiva; un administrador debe activarla desde "
        "la sección Usuarios para que puedas ingresar.",
    )
    st.session_state.auth_view = "login"
    st.rerun()
