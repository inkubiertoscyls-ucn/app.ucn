"""Componentes de autenticación"""
import streamlit as st
from services.usuarios import UsuariosService
from core.exceptions import AuthenticationError, InvalidRUTError

def login_form():
    """Formulario de inicio de sesión"""
    st.markdown("""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h1 style='color: #D9468D; font-size: 2.5rem; margin: 0; font-weight: 700;'>INKUBIERTOS</h1>
        <p style='color: #666; margin: 0.5rem 0 0 0;'>Sistema de Gestión de Inventario</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        rut = st.text_input("RUT", placeholder="Ej: 12345678-9", key="login_rut")
        password = st.text_input("Contraseña", type="password", placeholder="Ingrese su contraseña", key="login_pass")
        
        submitted = st.form_submit_button("Ingresar", use_container_width=True, type="primary")
        
        if submitted:
            if not rut or not password:
                st.error("Por favor ingrese RUT y contraseña")
                return False
            
            try:
                usuarios_service = UsuariosService()
                user = usuarios_service.autenticar(rut, password)
                st.session_state.logged_in = True
                st.session_state.user = {
                    'rut_usuario': user.get('rut_usuario'),
                    'nombre_usuario': user.get('nombre_usuario'),
                    'rol': user.get('rol'),
                    'area_asignada': user.get('area_asignada'),
                    'activo': user.get('activo')
                }
                st.session_state.page = 'inicio'
                return True
            except AuthenticationError as e:
                st.error(str(e))
                return False
            except InvalidRUTError:
                st.error("RUT inválido")
                return False
            except Exception as e:
                st.error("Error de conexión. Intente nuevamente.")
                return False
    
    return False
