"""
Tests for permissions between Administrador and Operario.
"""
import pytest
from unittest.mock import MagicMock, patch
from services.usuarios import UsuariosService
from services.inventario import InventarioService
from core.exceptions import AuthorizationError


class TestPermisos:
    @patch('services.usuarios.UsuariosRepository')
    def test_admin_puede_gestionar_usuarios(self, mock_repo):
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "111111111",
            "rol": "Administrador",
            "activo": True
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        assert service.puede_gestionar_usuarios("111111111") == True
    
    @patch('services.usuarios.UsuariosRepository')
    def test_operario_no_puede_gestionar_usuarios(self, mock_repo):
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "222222222",
            "rol": "Operario",
            "activo": True
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        assert service.puede_gestionar_usuarios("222222222") == False
    
    @patch('services.usuarios.UsuariosRepository')
    def test_usuario_inactivo_sin_permisos(self, mock_repo):
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "333333333",
            "rol": "Administrador",
            "activo": False
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        assert service.verificar_permisos("333333333") == False
    
    @patch('services.usuarios.UsuariosRepository')
    def test_admin_y_operario_pueden_registrar_movimientos(self, mock_repo):
        mock_usr = MagicMock()
        # Admin
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "111111111",
            "rol": "Administrador",
            "activo": True
        }
        mock_repo.return_value = mock_usr
        service = UsuariosService()
        service.repo = mock_usr
        assert service.puede_registrar_movimientos("111111111") == True
        
        # Operario
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "222222222",
            "rol": "Operario",
            "activo": True
        }
        assert service.puede_registrar_movimientos("222222222") == True
    
    def test_rut_usuario_es_pk(self):
        from db.schema_check import EXPECTED_SCHEMA
        assert "rut_usuario" in EXPECTED_SCHEMA["dim_usuario"]
        assert "id_usuario" not in EXPECTED_SCHEMA["dim_usuario"]
    
    def test_rut_proveedor_es_pk(self):
        from db.schema_check import EXPECTED_SCHEMA
        assert "rut_proveedor" in EXPECTED_SCHEMA["dim_proveedor"]
        assert "id_proveedor" not in EXPECTED_SCHEMA["dim_proveedor"]
    
    def test_producto_sin_area_habitual(self):
        from db.schema_check import EXPECTED_SCHEMA
        assert "area_habitual" not in EXPECTED_SCHEMA["dim_producto"]
