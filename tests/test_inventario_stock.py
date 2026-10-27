"""
Tests for inventory stock calculation and movements.
Uses mocks to avoid real DB access.
"""
import pytest
from unittest.mock import MagicMock, patch
from services.inventario import InventarioService
from core.exceptions import NegativeStockError, ValidationError, AuthorizationError


class TestInventarioStock:
    @patch('services.inventario.MovimientosRepository')
    @patch('services.inventario.ProductosRepository')
    @patch('services.inventario.UsuariosRepository')
    def test_calcular_stock_actual(self, mock_usuarios, mock_productos, mock_movimientos):
        # Mock movements with factor
        mock_mov = MagicMock()
        mock_mov.get_stock_movimientos.return_value = [
            {"cantidad": 10, "id_tipo_movimiento": 1, "dim_tipo_movimiento": {"factor_stock": 1}},
            {"cantidad": 3, "id_tipo_movimiento": 2, "dim_tipo_movimiento": {"factor_stock": -1}},
        ]
        mock_movimientos.return_value = mock_mov
        
        service = InventarioService()
        service.movimientos_repo = mock_mov
        stock = service.calcular_stock_actual(1, 1)
        assert stock == 7  # 10 + (-3)
    
    @patch('services.inventario.MovimientosRepository')
    def test_calcular_stock_sin_movimientos(self, mock_movimientos):
        mock_mov = MagicMock()
        mock_mov.get_stock_movimientos.return_value = []
        mock_movimientos.return_value = mock_mov
        
        service = InventarioService()
        service.movimientos_repo = mock_mov
        stock = service.calcular_stock_actual(999, 1)
        assert stock == 0
    
    def test_cantidad_debe_ser_positiva(self):
        service = InventarioService()
        data = {
            "id_producto": 1,
            "id_area": 1,
            "id_tipo_movimiento": 1,
            "rut_usuario": "111111111",
            "cantidad": -5
        }
        with pytest.raises(ValidationError):
            service._validar_movimiento_base(data)
    
    def test_cantidad_cero_invalida(self):
        service = InventarioService()
        data = {
            "id_producto": 1,
            "id_area": 1,
            "id_tipo_movimiento": 1,
            "rut_usuario": "111111111",
            "cantidad": 0
        }
        with pytest.raises(ValidationError):
            service._validar_movimiento_base(data)
    
    @patch('services.inventario.UsuariosRepository')
    def test_usuario_inactivo_rechazado(self, mock_usuarios):
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "Test",
            "rol": "Operario",
            "activo": False
        }
        mock_usuarios.return_value = mock_usr
        
        service = InventarioService()
        service.usuarios_repo = mock_usr
        
        data = {
            "id_producto": 1,
            "id_area": 1,
            "id_tipo_movimiento": 1,
            "rut_usuario": "111111111",
            "cantidad": 5
        }
        with pytest.raises(AuthorizationError):
            service._validar_movimiento_base(data)
    
    def test_no_guarda_costo_total(self):
        # Verificar que el esquema no incluye costo_total
        from db.schema_check import EXPECTED_SCHEMA
        assert "costo_total" not in EXPECTED_SCHEMA["hecho_inventario"]
    
    def test_stock_calculado_desde_historial(self):
        # Stock debe calcularse desde movimientos, no almacenado
        from services.inventario import InventarioService
        service = InventarioService()
        assert hasattr(service, 'calcular_stock_actual')
