"""
Pytest configuration and fixtures.
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def _sin_cache_datos(monkeypatch):
    """Evita que la caché de Streamlit filtre resultados entre pruebas."""
    monkeypatch.setenv("INK_DISABLE_CACHE", "1")


@pytest.fixture(autouse=True)
def _sesion_sin_revalidar(request, monkeypatch):
    """Las pruebas de interfaz usan usuarios ficticios que no existen en la BD.

    La revalidación periódica de la sesión se reemplaza por una que acepta la
    cuenta tal cual; `test_correcciones.py` prueba la revalidación real.
    """
    if request.node.get_closest_marker("revalidacion_real"):
        return
    import ui.state

    monkeypatch.setattr(ui.state, "_revalidar_usuario", lambda user: None)


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for tests."""
    mock = MagicMock()
    return mock


@pytest.fixture
def datos_usuario_admin():
    """Mock admin user data."""
    return {
        "rut_usuario": "12345678-9",
        "nombre_usuario": "Admin Test",
        "rol": "Administrador",
        "area_asignada": 1,
        "activo": True
    }


@pytest.fixture
def datos_usuario_operario():
    """Mock operator user data."""
    return {
        "rut_usuario": "11111111-1",
        "nombre_usuario": "Operario Test",
        "rol": "Operario",
        "area_asignada": 1,
        "activo": True
    }


@pytest.fixture
def datos_producto():
    """Mock product data."""
    return {
        "id_producto": 1,
        "nombre_producto": "Producto Test",
        "categoria": "Bebidas",
        "unidad_medida": "UN",
        "costo_base": 1000,
        "stock_minimo": 10,
        "stock_maximo": 100,
        "activo": True
    }


@pytest.fixture
def datos_movimiento_entrada():
    """Mock entry movement data."""
    return {
        "id_producto": 1,
        "id_area": 1,
        "id_tipo_movimiento": 1,
        "rut_usuario": "12345678-9",
        "cantidad": 10,
        "costo_unitario": 1000,
        "observacion": "Compra test"
    }
