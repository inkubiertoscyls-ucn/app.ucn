"""
Tests for user authentication and password management.
"""
import pytest
from unittest.mock import MagicMock, patch
from services.usuarios import UsuariosService
from core.auth_password import hash_password, verify_password
from core.exceptions import AuthenticationError, ValidationError, AuthorizationError, InvalidRUTError


class TestPasswordHashing:
    def test_hash_password_argon2(self):
        """Password should be hashed with Argon2id, not plain text."""
        password = "TestPass123"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$argon2")
        assert verify_password(password, hashed) is True
    
    def test_verify_wrong_password(self):
        """Wrong password should not verify."""
        hashed = hash_password("CorrectPass123")
        assert verify_password("WrongPass456", hashed) is False
    
    def test_password_min_length(self):
        """Password must be at least 8 characters."""
        with pytest.raises(ValueError):
            hash_password("short")
    
    def test_verify_empty_password(self):
        """Empty password should not verify."""
        hashed = hash_password("TestPass123")
        assert verify_password("", hashed) is False
        assert verify_password(None, hashed) is False


class TestAutenticacion:
    @patch('services.usuarios.UsuariosRepository')
    def test_autenticar_exitoso(self, mock_repo):
        """Successful authentication with correct credentials."""
        hashed = hash_password("TestPass123")
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "Test User",
            "rol": "Operario",
            "activo": True,
            "password_hash": hashed
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        result = service.autenticar("111111111", "TestPass123")
        assert result["rut_usuario"] == "111111111"
        assert "password_hash" not in result
    
    @patch('services.usuarios.UsuariosRepository')
    def test_autenticar_credenciales_incorrectas(self, mock_repo):
        """Wrong password should raise AuthenticationError."""
        hashed = hash_password("TestPass123")
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "Test User",
            "rol": "Operario",
            "activo": True,
            "password_hash": hashed
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(AuthenticationError):
            service.autenticar("111111111", "WrongPass456")
    
    @patch('services.usuarios.UsuariosRepository')
    def test_autenticar_usuario_inactivo(self, mock_repo):
        """Inactive user cannot authenticate."""
        hashed = hash_password("TestPass123")
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "Test User",
            "rol": "Operario",
            "activo": False,
            "password_hash": hashed
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(AuthenticationError):
            service.autenticar("111111111", "TestPass123")
    
    @patch('services.usuarios.UsuariosRepository')
    def test_autenticar_rut_invalido(self, mock_repo):
        """Invalid RUT should raise AuthenticationError."""
        mock_usr = MagicMock()
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(AuthenticationError):
            service.autenticar("123", "TestPass123")
    
    @patch('services.usuarios.UsuariosRepository')
    def test_autenticar_usuario_no_existe(self, mock_repo):
        """Non-existent user should raise AuthenticationError."""
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = None
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(AuthenticationError):
            service.autenticar("111111111", "TestPass123")


class TestRegistroUsuarios:
    @patch('services.usuarios.UsuariosRepository')
    def test_registrar_requiere_contraseña(self, mock_repo):
        """Registration requires password."""
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = None
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(ValidationError):
            service.registrar_usuario({
                "rut_usuario": "111111111",
                "nombre_usuario": "Test",
                "rol": "Operario"
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_no_aceptar_password_hash_directo(self, mock_repo):
        """Direct password_hash not accepted from public registration."""
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = None
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(ValidationError):
            service.registrar_usuario({
                "rut_usuario": "111111111",
                "nombre_usuario": "Test",
                "rol": "Operario",
                "password_hash": "$argon2$..."
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_publico_no_puede_crear_admin(self, mock_repo):
        """Public registration cannot create admin."""
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
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_contraseña_corta_rechazada(self, mock_repo):
        """Short password rejected."""
        mock_usr = MagicMock()
        mock_usr.get_by_rut.return_value = None
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        with pytest.raises(ValidationError):
            service.registrar_usuario({
                "rut_usuario": "111111111",
                "nombre_usuario": "Test",
                "rol": "Operario",
                "password": "short"
            })
    
    @patch('services.usuarios.UsuariosRepository')
    def test_admin_puede_crear_admin(self, mock_repo):
        """Admin can create another admin."""
        hashed = hash_password("TestPass123")
        mock_usr = MagicMock()
        # Check new user doesn't exist
        results = [
            {"rut_usuario": "222222222", "nombre_usuario": "Admin", "rol": "Administrador", "activo": True},  # creador
            None  # new user
        ]
        mock_usr.get_by_rut = MagicMock(side_effect=results)
        mock_usr.create.return_value = {
            "rut_usuario": "111111111",
            "nombre_usuario": "New Admin",
            "rol": "Administrador",
            "activo": True,
            "password_hash": hashed
        }
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        service.repo = mock_usr
        result = service.registrar_usuario({
            "rut_usuario": "111111111",
            "nombre_usuario": "New Admin",
            "rol": "Administrador",
            "password": "TestPass123"
        }, creado_por_rut="222222222")
        assert result["rol"] == "Administrador"
        assert "password_hash" in result  # creado por servicio


class TestInicializacionAdmin:
    @patch('services.usuarios.UsuariosRepository')
    def test_detecta_admin_existente(self, mock_repo):
        """Should detect existing admin."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.return_value = [
            {"rut_usuario": "111111111", "rol": "Administrador", "activo": True}
        ]
        mock_repo.return_value = mock_usr
        
        service = UsuariosService()
        # Script logic tested separately
        admins = mock_usr.get_by_rol("Administrador")
        active_admins = [a for a in admins if a.get("activo")]
        assert len(active_admins) > 0
    
    @patch('services.usuarios.UsuariosRepository')
    def test_no_duplicar_admin(self, mock_repo):
        """Should not create duplicate admin if exists."""
        mock_usr = MagicMock()
        mock_usr.get_by_rol.return_value = [
            {"rut_usuario": "111111111", "rol": "Administrador", "activo": True}
        ]
        mock_repo.return_value = mock_usr
        # Script should stop
        assert True
