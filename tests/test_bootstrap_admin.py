"""
Tests for first administrator bootstrap.
"""
import pytest
from unittest.mock import MagicMock, patch
from services.usuarios import UsuariosService
from core.auth_password import hash_password, verify_password
from core.exceptions import AuthorizationError, ValidationError


class TestBootstrapPrimerAdministrador:
    @patch('services.usuarios.UsuariosRepository')
    def test_crear_primer_admin_cuando_no_existe(self, mock_repo):
        """Should create first admin when no admins exist."""
        mock_usr = MagicMock()
        # No admins exist
        mock_usr.get_by_rol.return_value = []
        # New user doesn't exist
        mock_usr.get_by_rut.return_value = None
        hashed = hash_password("TestPass123")
        mock_usr.create.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "Admin Test",
            "rol": "Administrador",
            "area_asignada": "Todas",
            "activo": True,
            "password_hash": hashed
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        result = service.crear_primer_administrador({
            "rut_usuario": "111111111",
            "nombre_usuario": "Admin Test",
            "password": "TestPass123"
        })
        assert result["rol"] == "Administrador"
        assert result["activo"] is True
        assert result.get("area_asignada") == "Todas"
        assert "password_hash" in result
        # Check create was called without plain password and with area_asignada
        call_args = mock_usr.create.call_args[0][0]
        assert "password" not in call_args
        assert call_args.get("area_asignada") == "Todas"
    
    @patch('services.usuarios.UsuariosRepository')
    def test_rechazar_si_ya_existe_admin(self, mock_repo):
        """Should reject bootstrap if admin already exists."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.return_value = [
            {"rut_usuario": "222222222", "rol": "Administrador", "activo": True}
        ]
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(AuthorizationError):
            service.crear_primer_administrador({
                "rut_usuario": "111111111",
                "nombre_usuario": "Admin Test",
                "password": "TestPass123"
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_rechazar_rut_invalido(self, mock_repo):
        """Should reject invalid RUT."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.return_value = []
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(Exception):  # ValidationError or InvalidRUTError
            service.crear_primer_administrador({
                "rut_usuario": "123",
                "nombre_usuario": "Admin Test",
                "password": "TestPass123"
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_guardar_solo_hash_argon2(self, mock_repo):
        """Should store only Argon2id hash, no plain password."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.return_value = []
        mock_usr.get_by_rut.return_value = None
        password = "TestPass123"
        hashed = hash_password(password)
        mock_usr.create.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "Admin Test",
            "rol": "Administrador",
            "activo": True,
            "password_hash": hashed
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        result = service.crear_primer_administrador({
            "rut_usuario": "111111111",
            "nombre_usuario": "Admin Test",
            "password": password
        })
        assert result["password_hash"].startswith("$argon2")
        call_args = mock_usr.create.call_args[0][0]
        assert "password" not in call_args
        assert verify_password(password, result["password_hash"]) is True
    
    @patch('services.usuarios.UsuariosRepository')
    def test_conserva_restricciones_flujo_normal(self, mock_repo):
        """Normal flow still requires admin to create admin."""
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = None
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(AuthorizationError):
            service.registrar_usuario({
                "rut_usuario": "111111111",
                "nombre_usuario": "Test",
                "rol": "Administrador",
                "password": "TestPass123"
            })  # No creado_por_rut
    
    @patch('services.usuarios.UsuariosRepository')
    def test_rechazar_password_corta(self, mock_repo):
        """Short password rejected in bootstrap."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.return_value = []
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(ValidationError):
            service.crear_primer_administrador({
                "rut_usuario": "111111111",
                "nombre_usuario": "Admin Test",
                "password": "short"
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_manejar_error_supabase_al_verificar_admins(self, mock_repo):
        """Should handle Supabase errors when checking admins."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.side_effect = Exception("Connection error")
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(ValidationError):
            service.crear_primer_administrador({
                "rut_usuario": "111111111",
                "nombre_usuario": "Admin Test",
                "password": "TestPass123"
            })
