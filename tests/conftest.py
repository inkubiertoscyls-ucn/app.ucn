"""
Pytest configuration and fixtures.
"""
import pytest
from unittest.mock import MagicMock


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
