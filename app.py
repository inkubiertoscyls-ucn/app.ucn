"""
INKubiertos - Sistema de Gestión de Inventario
Frontend Streamlit alineado progresivamente al mockup de Figma.
"""
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from components.navigation import sidebar_navigation
from ui.layout import page_header, top_bar
from ui.state import init_state, require_role
from ui.theme import inject_theme
from views.auth import render_auth
from views.alertas import render_alertas
from views.eventos import render_eventos
from views.fudo import render_fudo
from views.inicio import render_inicio
from views.inventario import render_inventario
from views.movimientos import render_movimientos
from views.productos import render_productos
from views.proveedores import render_proveedores
from views.rentabilidad import render_rentabilidad
from views.usuarios import render_usuarios

# Page config
st.set_page_config(
    page_title="INKubiertos · Inventario",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()
init_state()


def show_usuarios():
    require_role("Administrador")
    render_usuarios()


# Main app
def main():
    if not st.session_state.logged_in:
        render_auth()
        return

    sidebar_navigation()
    top_bar(st.session_state.user)

    page = st.session_state.page

    if page == "inicio":
        render_inicio()
    elif page in {"entrada", "salida", "historial", "movimientos"}:
        render_movimientos()
    elif page == "inventario":
        render_inventario()
    elif page == "alertas":
        render_alertas()
    elif page == "rentabilidad":
        render_rentabilidad()
    elif page == "productos":
        render_productos()
    elif page == "proveedores":
        render_proveedores()
    elif page == "eventos":
        render_eventos()
    elif page == "fudo":
        render_fudo()
    elif page == "usuarios":
        show_usuarios()
    else:
        render_inicio()


if __name__ == "__main__":
    main()
