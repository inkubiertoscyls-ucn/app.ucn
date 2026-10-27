"""
INKubiertos - Sistema de Gestión de Inventario
Frontend profesional y minimalista con Streamlit
"""
import streamlit as st
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from components.auth import login_form
from components.navigation import sidebar_navigation

# Page config
st.set_page_config(
    page_title="INKubiertos - Sistema de Inventario",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS profesional y minimalista
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .stApp {
        background-color: #f8f9fa;
    }
    
    [data-testid="stSidebar"] {
        background-color: #1e1e1e;
        border-right: 1px solid #2d2d2d;
    }
    
    [data-testid="stSidebar"] .stButton > button {
        background-color: transparent;
        color: #e0e0e0;
        border: none;
        border-radius: 6px;
        text-align: left;
        justify-content: flex-start;
        padding: 0.625rem 0.875rem;
        font-weight: 500;
        font-size: 0.875rem;
        margin-bottom: 0.25rem;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #2d2d2d;
        color: #ffffff;
    }
    
    .stButton > button[kind="primary"] {
        background-color: #D9468D;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.625rem 1.25rem;
        font-weight: 600;
        font-size: 0.875rem;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #B83272;
    }
    
    .stButton > button {
        background-color: white;
        color: #1e1e1e;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 0.625rem 1.25rem;
        font-weight: 500;
        font-size: 0.875rem;
    }
    
    .stButton > button:hover {
        background-color: #f8f9fa;
        border-color: #adb5bd;
    }
    
    .metric-card {
        background: white;
        padding: 1.25rem 1.5rem;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    }
    
    .metric-label {
        color: #6c757d;
        font-size: 0.8125rem;
        font-weight: 500;
        margin-bottom: 0.375rem;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }
    
    .metric-value {
        color: #212529;
        font-size: 1.875rem;
        font-weight: 700;
        line-height: 1.2;
    }
    
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 6px;
        border: 1px solid #ced4da;
        font-size: 0.875rem;
    }
    
    .stTextInput > label,
    .stSelectbox > label,
    .stNumberInput > label,
    .stTextArea > label {
        font-weight: 500;
        color: #212529;
        font-size: 0.875rem;
    }
    
    h1 {
        color: #212529;
        font-weight: 700;
        font-size: 1.75rem;
        margin-bottom: 0.25rem;
    }
    
    h2 {
        color: #212529;
        font-weight: 600;
        font-size: 1.375rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    
    h3 {
        color: #212529;
        font-weight: 600;
        font-size: 1.125rem;
    }
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    [data-testid="stForm"] {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'page' not in st.session_state:
    st.session_state.page = 'inicio'


def show_login_page():
    """Página de inicio de sesión"""
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("""
        <div style='text-align: center; margin-bottom: 2rem;'>
            <h1 style='color: #D9468D; font-size: 2rem; margin: 0; font-weight: 700; letter-spacing: -0.02em;'>INKUBIERTOS</h1>
            <p style='color: #6c757d; margin: 0.375rem 0 0 0; font-size: 0.875rem;'>Sistema de Gestión de Inventario</p>
        </div>
        """, unsafe_allow_html=True)
        login_form()


def show_inicio_admin():
    """Inicio para administrador"""
    st.markdown("# Inicio")
    st.markdown("<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Panel general de gestión</p>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class='metric-card'>
            <div class='metric-label'>Productos activos</div>
            <div class='metric-value'>-</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class='metric-card'>
            <div class='metric-label'>Stock bajo</div>
            <div class='metric-value'>-</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class='metric-card'>
            <div class='metric-label'>Movimientos hoy</div>
            <div class='metric-value'>-</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class='metric-card'>
            <div class='metric-label'>Entradas hoy</div>
            <div class='metric-value'>-</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("## Accesos rápidos")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Registrar entrada", use_container_width=True, type="primary"):
            st.session_state.page = 'entrada'
            st.rerun()
    with col2:
        if st.button("Registrar salida", use_container_width=True, type="primary"):
            st.session_state.page = 'salida'
            st.rerun()
    with col3:
        if st.button("Ver inventario", use_container_width=True):
            st.session_state.page = 'inventario'
            st.rerun()
    with col4:
        if st.button("Gestionar productos", use_container_width=True):
            st.session_state.page = 'productos'
            st.rerun()
    
    st.markdown("## Movimientos recientes")
    st.info("No hay movimientos registrados.")


def show_inicio_operario():
    """Inicio para operario"""
    user = st.session_state.user
    st.markdown("# Inicio")
    st.markdown(f"<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Bienvenido, {user.get('nombre_usuario')}</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Registrar entrada", use_container_width=True, type="primary"):
            st.session_state.page = 'entrada'
            st.rerun()
    with col2:
        if st.button("Registrar salida", use_container_width=True, type="primary"):
            st.session_state.page = 'salida'
            st.rerun()
    with col3:
        if st.button("Ver historial", use_container_width=True):
            st.session_state.page = 'historial'
            st.rerun()
    
    st.markdown("## Inventario")
    st.info("Consulte el inventario y registre movimientos desde el menú lateral.")


def show_entrada():
    st.markdown("# Registrar entrada")
    st.markdown("<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Registro de entradas al inventario</p>", unsafe_allow_html=True)
    
    with st.form("entrada_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Producto", ["Seleccionar"])
            st.number_input("Cantidad", min_value=1, step=1)
            st.selectbox("Área", ["Seleccionar"])
        with col2:
            st.selectbox("Proveedor", ["Sin proveedor"])
            st.number_input("Costo unitario", min_value=0.0, step=0.01, format="%.2f")
            st.text_area("Observación")
        
        submitted = st.form_submit_button("Registrar entrada", use_container_width=True, type="primary")
        if submitted:
            st.info("Conectando con el servicio de inventario...")


def show_salida():
    st.markdown("# Registrar salida")
    st.markdown("<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Registro de salidas del inventario</p>", unsafe_allow_html=True)
    
    with st.form("salida_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Producto", ["Seleccionar"])
            st.number_input("Cantidad", min_value=1, step=1)
            st.selectbox("Área", ["Seleccionar"])
        with col2:
            st.selectbox("Evento", ["Sin evento"])
            st.text_area("Observación")
        
        submitted = st.form_submit_button("Registrar salida", use_container_width=True, type="primary")
        if submitted:
            st.info("Conectando con el servicio de inventario...")


def show_inventario():
    st.markdown("# Inventario")
    st.markdown("<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Consulta de existencias</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input("Buscar", placeholder="Nombre del producto")
    with col2:
        st.selectbox("Área", ["Todas"])
    with col3:
        st.selectbox("Estado", ["Todos", "Disponible", "Stock bajo", "Sin stock"])
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Los datos se cargarán desde el backend.")


def show_historial():
    st.markdown("# Historial de movimientos")
    st.markdown("<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Registro de movimientos</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.date_input("Desde")
    with col2:
        st.date_input("Hasta")
    with col3:
        st.selectbox("Tipo", ["Todos", "Entrada", "Salida", "Merma", "Ajuste"])
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Historial cargado desde el backend.")


def show_productos():
    user = st.session_state.user
    if user.get('rol') != 'Administrador':
        st.error("Acceso denegado")
        return
    st.markdown("# Productos")
    st.markdown("<p style='color: #6c757d; margin-top: -0.5rem; margin-bottom: 2rem;'>Gestión de productos</p>", unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    with col1:
        st.text_input("Buscar", placeholder="Nombre o categoría")
    with col2:
        st.button("Nuevo producto", use_container_width=True, type="primary")
    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Gestión de productos mediante servicios del backend.")


def show_proveedores():
    user = st.session_state.user
    if user.get('rol') != 'Administrador':
        st.error("Acceso denegado")
        return
    st.markdown("# Proveedores")
    st.info("Gestión de proveedores")


def show_eventos():
    user = st.session_state.user
    if user.get('rol') != 'Administrador':
        st.error("Acceso denegado")
        return
    st.markdown("# Artistas y eventos")
    st.info("Gestión de eventos")


def show_fudo():
    user = st.session_state.user
    if user.get('rol') != 'Administrador':
        st.error("Acceso denegado")
        return
    st.markdown("# Ventas de FUDO")
    st.info("Importación mediante FudoImportService")


def show_usuarios():
    user = st.session_state.user
    if user.get('rol') != 'Administrador':
        st.error("Acceso denegado")
        return
    st.markdown("# Usuarios")
    st.info("Gestión de usuarios. Primer administrador creado con scripts/init_admin.py")


# Main app
def main():
    if not st.session_state.logged_in:
        show_login_page()
        return
    
    sidebar_navigation()
    
    user = st.session_state.user
    page = st.session_state.page
    
    if page == 'inicio':
        if user.get('rol') == 'Administrador':
            show_inicio_admin()
        else:
            show_inicio_operario()
    elif page == 'entrada':
        show_entrada()
    elif page == 'salida':
        show_salida()
    elif page == 'inventario':
        show_inventario()
    elif page == 'historial':
        show_historial()
    elif page == 'productos':
        show_productos()
    elif page == 'proveedores':
        show_proveedores()
    elif page == 'eventos':
        show_eventos()
    elif page == 'fudo':
        show_fudo()
    elif page == 'usuarios':
        show_usuarios()
    else:
        if user.get('rol') == 'Administrador':
            show_inicio_admin()
        else:
            show_inicio_operario()


if __name__ == "__main__":
    main()
