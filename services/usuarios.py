"""
Usuarios service - Business logic for users, permissions.
"""
from typing import List, Dict, Optional
from repositories.usuarios import UsuariosRepository
from core.exceptions import ValidationError, NotFoundError, AuthorizationError, InvalidRUTError, AuthenticationError
from core.utils import normalizar_rut, validar_rut
from core.auth_password import hash_password, verify_password


class UsuariosService:
    def __init__(self):
        self.repo = UsuariosRepository()
    
    def listar_usuarios(self, solo_activos: bool = False) -> List[Dict]:
        """List users."""
        if solo_activos:
            return self.repo.get_activos()
        return self.repo.get_all()
    
    def consultar_usuario(self, rut: str) -> Optional[Dict]:
        """Get user by RUT."""
        return self.repo.get_by_rut(rut)
    
    def registrar_usuario(self, data: Dict, creado_por_rut: str = None) -> Dict:
        """Register new user."""
        self._validar_usuario(data)
        rut_norm = normalizar_rut(data["rut_usuario"])
        
        # Password is required for new accounts
        if "password_hash" in data and "password" not in data:
            raise ValidationError("No se acepta password_hash directo desde registro público")
        if "password" not in data or not data.get("password"):
            raise ValidationError("Contraseña es requerida")
        
        # Prevent public admin creation
        if data.get("rol") == "Administrador":
            if not creado_por_rut:
                raise AuthorizationError("Solo un administrador autorizado puede crear cuentas de Administrador")
            creador = self.repo.get_by_rut(normalizar_rut(creado_por_rut))
            if not creador or not creador.get("activo") or creador.get("rol") != "Administrador":
                raise AuthorizationError("Solo un administrador autorizado puede crear cuentas de Administrador")
        
        if self.repo.get_by_rut(rut_norm):
            raise ValidationError("Ya existe un usuario con ese RUT")
        data["rut_usuario"] = rut_norm
        
        # Hash password securely
        try:
            data["password_hash"] = hash_password(data["password"])
        except ValueError as e:
            raise ValidationError(str(e))
        except Exception:
            raise ValidationError("Error al procesar contraseña")
        
        # Remove plain password
        data.pop("password", None)
        # Ensure no direct hash injection
        if "password_hash" not in data or not data["password_hash"]:
            raise ValidationError("Error al generar hash de contraseña")
        
        return self.repo.create(data)
    
    def crear_primer_administrador(self, data: Dict) -> Dict:
        """Create first administrator only if no administrator exists. For local bootstrap only."""
        # Check if any administrator exists
        try:
            admins = self.repo.get_by_rol("Administrador")
            if admins and len(admins) > 0:
                raise AuthorizationError("Ya existe un administrador. Use el proceso normal de autorización.")
        except AuthorizationError:
            raise
        except Exception as e:
            raise ValidationError(f"Error al verificar administradores existentes: {e}")
        
        if not data.get("rut_usuario"):
            raise ValidationError("RUT es requerido")
        if not data.get("nombre_usuario") or not str(data["nombre_usuario"]).strip():
            raise ValidationError("Nombre de usuario es requerido")
        
        try:
            rut_norm = normalizar_rut(data["rut_usuario"])
            if not validar_rut(rut_norm):
                raise InvalidRUTError("RUT inválido")
        except (InvalidRUTError, ValidationError):
            raise
        except Exception as e:
            raise ValidationError(f"RUT inválido: {e}")
        
        if "password" not in data or not data.get("password"):
            raise ValidationError("Contraseña es requerida")
        
        if self.repo.get_by_rut(rut_norm):
            raise ValidationError("Ya existe un usuario con ese RUT")
        
        user_data = {
            "rut_usuario": rut_norm,
            "nombre_usuario": str(data["nombre_usuario"]).strip(),
            "rol": "Administrador",
            "area_asignada": "Todas",
            "activo": True,
        }
        
        try:
            user_data["password_hash"] = hash_password(data["password"])
        except ValueError as e:
            raise ValidationError(str(e))
        except Exception:
            raise ValidationError("Error al procesar contraseña")
        
        if "password_hash" not in user_data or not user_data["password_hash"]:
            raise ValidationError("Error al generar hash de contraseña")
        
        return self.repo.create(user_data)
    
    def autenticar(self, rut: str, password: str) -> Dict:
        """Authenticate user with RUT and password."""
        if not rut or not password:
            raise AuthenticationError("Credenciales inválidas")
        try:
            rut_norm = normalizar_rut(rut)
            if not validar_rut(rut_norm):
                raise InvalidRUTError("RUT inválido")
        except (InvalidRUTError, Exception):
            raise AuthenticationError("Credenciales inválidas")
        
        usuario = self.repo.get_by_rut(rut_norm)
        if not usuario:
            raise AuthenticationError("Credenciales inválidas")
        if not usuario.get("activo", False):
            raise AuthenticationError("Cuenta inactiva")
        
        password_hash = usuario.get("password_hash")
        if not password_hash:
            raise AuthenticationError("Credenciales inválidas")
        
        if not verify_password(password, password_hash):
            raise AuthenticationError("Credenciales inválidas")
        
        # Return user info without sensitive data
        usuario_seguro = dict(usuario)
        usuario_seguro.pop("password_hash", None)
        return usuario_seguro

    
    def modificar_usuario(self, rut: str, data: Dict, modificado_por_rut: str = None) -> Dict:
        """Modify user."""
        rut_norm = normalizar_rut(rut)
        usuario = self.consultar_usuario(rut_norm)
        if not usuario:
            raise NotFoundError("Usuario no encontrado")
        if modificado_por_rut:
            modificador = self.repo.get_by_rut(normalizar_rut(modificado_por_rut))
            if not modificador or not modificador.get("activo") or modificador.get("rol") != "Administrador":
                raise AuthorizationError("Solo administradores autorizados pueden modificar usuarios")
        if "rol" in data and data["rol"] not in ["Administrador", "Operario"]:
            raise ValidationError("Rol inválido. Debe ser 'Administrador' o 'Operario'")
        if "password" in data:
            try:
                data["password_hash"] = hash_password(data["password"])
            except ValueError as e:
                raise ValidationError(str(e))
            data.pop("password")
        if "password_hash" in data and "password" not in data:
            # Solo permitir cambio de password_hash vía password
            pass
        return self.repo.update("rut_usuario", rut_norm, data)
    
    def desactivar_usuario(self, rut: str) -> Dict:
        """Deactivate user."""
        rut_norm = normalizar_rut(rut)
        usuario = self.consultar_usuario(rut_norm)
        if not usuario:
            raise NotFoundError("Usuario no encontrado")
        return self.repo.deactivate("rut_usuario", rut_norm)
    
    def activar_usuario(self, rut: str) -> Dict:
        """Activate user."""
        rut_norm = normalizar_rut(rut)
        usuario = self.consultar_usuario(rut_norm)
        if not usuario:
            raise NotFoundError("Usuario no encontrado")
        return self.repo.update("rut_usuario", rut_norm, {"activo": True})
    
    def verificar_permisos(self, rut: str, requiere_admin: bool = False) -> bool:
        """Verify user permissions."""
        usuario = self.consultar_usuario(rut)
        if not usuario:
            return False
        if not usuario.get("activo", False):
            return False
        if requiere_admin:
            return usuario.get("rol") == "Administrador"
        return usuario.get("rol") in ["Administrador", "Operario"]
    
    def puede_gestionar_usuarios(self, rut: str) -> bool:
        """Check if user can manage users (Admin only)."""
        return self.verificar_permisos(rut, requiere_admin=True)
    
    def puede_registrar_movimientos(self, rut: str) -> bool:
        """Check if user can register movements."""
        usuario = self.consultar_usuario(rut)
        if not usuario:
            return False
        return usuario.get("activo", False) and usuario.get("rol") in ["Administrador", "Operario"]
    
    def _validar_usuario(self, data: Dict) -> None:
        """Validate user data."""
        if not data.get("rut_usuario"):
            raise ValidationError("RUT es requerido")
        try:
            rut_norm = normalizar_rut(data["rut_usuario"])
            if not validar_rut(rut_norm):
                raise InvalidRUTError("RUT inválido")
        except InvalidRUTError:
            raise
        except Exception as e:
            raise ValidationError(f"RUT inválido: {e}")
        
        if not data.get("nombre_usuario") or not str(data["nombre_usuario"]).strip():
            raise ValidationError("Nombre de usuario es requerido")
        if not data.get("rol"):
            raise ValidationError("Rol es requerido")
        if data["rol"] not in ["Administrador", "Operario"]:
            raise ValidationError("Rol inválido. Debe ser 'Administrador' o 'Operario'")
    
    def autorizar_cuenta(self, rut: str, autorizar_por: str) -> Dict:
        """Authorize account (if auth mechanism exists)."""
        # Documentar integración con sistema de auth existente
        autoriza = self.consultar_usuario(autorizar_por)
        if not autoriza or not autoriza.get("activo") or autoriza.get("rol") != "Administrador":
            raise AuthorizationError("Solo administradores pueden autorizar cuentas")
        return self.activar_usuario(rut)
