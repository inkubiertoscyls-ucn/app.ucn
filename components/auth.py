"""Componentes de autenticación."""
import streamlit as st

from core.exceptions import AuthenticationError, InvalidRUTError
from services.usuarios import UsuariosService


def login_form():
    """Formulario de inicio de sesión."""
    with st.form("login_form", clear_on_submit=False):
        rut = st.text_input(
            "RUT",
            placeholder="Ej: 12.345.678-5",
            key="login_rut",
            autocomplete="username",
        )
        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="Ingresa tu contraseña",
            key="login_pass",
            autocomplete="current-password",
        )

        submitted = st.form_submit_button(
            "Ingresar",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            rut = (rut or "").strip()
            if not rut or not password:
                st.error("Por favor ingresa RUT y contraseña.")
                return False

            try:
                usuarios_service = UsuariosService()
                user = usuarios_service.autenticar(rut, password)
                st.session_state.logged_in = True
                st.session_state.user = {
                    "rut_usuario": user.get("rut_usuario"),
                    "nombre_usuario": user.get("nombre_usuario"),
                    "rol": user.get("rol"),
                    "area_asignada": user.get("area_asignada"),
                    "activo": user.get("activo"),
                }
                st.session_state.page = "inicio"
                st.session_state.auth_view = "login"
                st.rerun()
            except InvalidRUTError:
                st.error("RUT inválido. Revisa el formato e inténtalo nuevamente.")
            except AuthenticationError as error:
                mensaje = str(error)
                if mensaje == "Cuenta inactiva":
                    mensaje = (
                        "Tu cuenta está inactiva. Contacta al administrador "
                        "para que active tu acceso."
                    )
                st.error(mensaje)
            except Exception:
                st.error("No se pudo conectar con el servicio. Intenta nuevamente.")

    return False
