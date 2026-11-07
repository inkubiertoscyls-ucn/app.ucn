"""Navegación lateral de INKubiertos."""
from __future__ import annotations

from html import escape
from typing import Any, Dict

import streamlit as st

from ui.format import area_visible
from ui.state import logout

# Las pantallas heredadas de entrada/salida/historial se agrupan visualmente
# bajo Movimientos hasta que exista la pantalla unificada.
PAGE_ALIASES = {
    "entrada": "movimientos",
    "salida": "movimientos",
    "historial": "movimientos",
}


def _nav_button(label: str, page: str, active: bool) -> None:
    if st.sidebar.button(
        label,
        key=f"nav_{page}",
        use_container_width=True,
        type="primary" if active else "secondary",
    ):
        st.session_state.page = page
        st.rerun()


def _user_block(user: Dict[str, Any]) -> str:
    nombre = escape(str(user.get("nombre_usuario") or "Usuario"))
    rol = escape(str(user.get("rol") or ""))
    area = escape(area_visible(user.get("area_asignada")))
    detalle = f"{rol} · {area}" if area and rol == "Operario" else rol
    return f"""
    <div class="ink-sidebar-user">
        <div class="ink-sidebar-user-name">{nombre}</div>
        <div class="ink-sidebar-user-role">{detalle}</div>
    </div>
    """


def sidebar_navigation() -> None:
    """Renderiza el menú lateral según el rol de la sesión."""
    user = st.session_state.get("user")
    if not user:
        return

    rol = user.get("rol")
    page = st.session_state.get("page", "inicio")
    active_page = PAGE_ALIASES.get(page, page)

    with st.sidebar:
        st.markdown(
            """
            <div class="ink-sidebar-brand">
                <div class="ink-sidebar-wordmark">INKubiertos</div>
                <div class="ink-sidebar-subtitle">Gestión de inventario</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(_user_block(user), unsafe_allow_html=True)

        st.markdown('<div class="ink-sidebar-label">Navegación</div>', unsafe_allow_html=True)
        _nav_button("Inicio", "inicio", active_page == "inicio")
        _nav_button("Inventario", "inventario", active_page == "inventario")
        _nav_button("Movimientos", "movimientos", active_page == "movimientos")
        _nav_button("Alertas", "alertas", active_page == "alertas")

        if rol == "Administrador":
            _nav_button("Rentabilidad", "rentabilidad", active_page == "rentabilidad")
            st.markdown(
                '<div class="ink-sidebar-rule"></div>'
                '<div class="ink-sidebar-label">Administración</div>',
                unsafe_allow_html=True,
            )
            _nav_button("Productos", "productos", active_page == "productos")
            _nav_button("Proveedores", "proveedores", active_page == "proveedores")
            _nav_button("Artistas y eventos", "eventos", active_page == "eventos")
            _nav_button("Ventas de FUDO", "fudo", active_page == "fudo")
            _nav_button("Usuarios", "usuarios", active_page == "usuarios")

        st.markdown('<div class="ink-sidebar-spacer"></div>', unsafe_allow_html=True)

        if st.button("Cerrar sesión", key="nav_logout", use_container_width=True):
            logout()
            st.rerun()
