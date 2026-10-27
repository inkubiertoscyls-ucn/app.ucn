"""Navegación lateral"""
import streamlit as st

def sidebar_navigation():
    """Barra lateral de navegación"""
    user = st.session_state.get('user')
    if not user:
        return
    
    rol = user.get('rol')
    nombre = user.get('nombre_usuario', '')
    
    st.sidebar.markdown("""
    <div style='padding: 1.25rem 1rem 1rem 1rem;'>
        <div style='color: #D9468D; font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em;'>INKUBIERTOS</div>
        <div style='color: #adb5bd; font-size: 0.75rem; margin-top: 0.25rem;'>Sistema de Inventario</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
    <div style='padding: 0 1rem 1rem 1rem;'>
        <div style='color: #ffffff; font-size: 0.875rem; font-weight: 500;'>{nombre}</div>
        <div style='color: #adb5bd; font-size: 0.75rem;'>{rol}</div>
    </div>
    <hr style='border-color: #2d2d2d; margin: 0 0 0.75rem 0;'>
    """, unsafe_allow_html=True)
    
    # Menú según rol
    if st.sidebar.button("Inicio", use_container_width=True, key="nav_inicio"):
        st.session_state.page = 'inicio'
        st.rerun()
    
    if st.sidebar.button("Inventario", use_container_width=True, key="nav_inventario"):
        st.session_state.page = 'inventario'
        st.rerun()
    
    if st.sidebar.button("Registrar entrada", use_container_width=True, key="nav_entrada"):
        st.session_state.page = 'entrada'
        st.rerun()
    
    if st.sidebar.button("Registrar salida", use_container_width=True, key="nav_salida"):
        st.session_state.page = 'salida'
        st.rerun()
    
    if st.sidebar.button("Historial de movimientos", use_container_width=True, key="nav_historial"):
        st.session_state.page = 'historial'
        st.rerun()
    
    if rol == 'Administrador':
        st.sidebar.markdown("<hr style='border-color: #2d2d2d; margin: 1rem 0 0.75rem 0;'>", unsafe_allow_html=True)
        st.sidebar.markdown("<div style='color: #6c757d; font-size: 0.75rem; padding: 0 1rem; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em;'>Administración</div>", unsafe_allow_html=True)
        
        if st.sidebar.button("Productos", use_container_width=True, key="nav_productos"):
            st.session_state.page = 'productos'
            st.rerun()
        
        if st.sidebar.button("Proveedores", use_container_width=True, key="nav_proveedores"):
            st.session_state.page = 'proveedores'
            st.rerun()
        
        if st.sidebar.button("Artistas y eventos", use_container_width=True, key="nav_eventos"):
            st.session_state.page = 'eventos'
            st.rerun()
        
        if st.sidebar.button("Ventas de FUDO", use_container_width=True, key="nav_fudo"):
            st.session_state.page = 'fudo'
            st.rerun()
        
        if st.sidebar.button("Usuarios", use_container_width=True, key="nav_usuarios"):
            st.session_state.page = 'usuarios'
            st.rerun()
    
    st.sidebar.markdown("<div style='position: fixed; bottom: 1.5rem; left: 1rem; right: 1rem;'>", unsafe_allow_html=True)
    if st.sidebar.button("Cerrar sesión", use_container_width=True, key="nav_logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.page = 'login'
        st.rerun()
    st.sidebar.markdown("</div>", unsafe_allow_html=True)
