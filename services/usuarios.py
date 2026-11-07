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
        """Register new user.

        El registro público solo puede crear Operarios. Las cuentas de
        Operario siempre nacen inactivas y solo un administrador las habilita.
        La creación de Administradores exige un administrador autorizado.
        """
        datos = dict(data)
        self._validar_usuario(datos)
        rut_norm = normalizar_rut(datos["rut_usuario"])

        # Password is required for new accounts
        if "password_hash" in datos and "password" not in datos:
            raise ValidationError("No se acepta password_hash directo desde registro público")
        if "password" not in datos or not datos.get("password"):
            raise ValidationError("Contraseña es requerida")

        if datos.get("rol") == "Administrador":
            # Prevent public admin creation.
            if not creado_por_rut:
                raise AuthorizationError("Solo un administrador autorizado puede crear cuentas de Administrador")
            self._administrador_autorizado(creado_por_rut)
            datos.setdefault("activo", True)
        else:
            # Ningún registro público puede autoasignarse otro rol ni activarse.
            datos["rol"] = "Operario"
            datos["activo"] = False

        if self.repo.get_by_rut(rut_norm):
            raise ValidationError("Ya existe un usuario con ese RUT")
        datos["rut_usuario"] = rut_norm

        # Hash password securely
        try:
            datos["password_hash"] = hash_password(datos["password"])
        except ValueError as e:
            raise ValidationError(str(e))
        except Exception:
            raise ValidationError("Error al procesar contraseña")

        # Remove plain password
        datos.pop("password", None)
        # Ensure no direct hash injection
        if "password_hash" not in datos or not datos["password_hash"]:
            raise ValidationError("Error al generar hash de contraseña")

        return self.repo.create(datos)
    
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
            self._administrador_autorizado(modificado_por_rut)
        if "rol" in data and data["rol"] not in ["Administrador", "Operario"]:
            raise ValidationError("Rol inválido. Debe ser 'Administrador' o 'Operario'")
        if "password" in data:
            try:
                data["password_hash"] = hash_password(data["password"])
            except ValueError as e:
                raise ValidationError(str(e))
            data.pop("password")
        return self.repo.update("rut_usuario", rut_norm, data)

    def activar_usuario(self, rut: str, autorizado_por: str = None) -> Dict:
        """Activate user. Un administrador activo debe autorizar la acción."""
        rut_norm = normalizar_rut(rut)
        usuario = self.consultar_usuario(rut_norm)
        if not usuario:
            raise NotFoundError("Usuario no encontrado")
        if autorizado_por is not None:
            self._administrador_autorizado(autorizado_por)
        if usuario.get("activo", False):
            return usuario
        return self.repo.update("rut_usuario", rut_norm, {"activo": True})

    def desactivar_usuario(self, rut: str, autorizado_por: str = None) -> Dict:
        """Deactivate user without deleting their history.

        Reglas de seguridad:
        - Solo un administrador activo puede autorizar la desactivación.
        - Un administrador no puede desactivar su propia cuenta.
        - Nunca se puede quedar el sistema sin administradores activos.
        """
        rut_norm = normalizar_rut(rut)
        usuario = self.consultar_usuario(rut_norm)
        if not usuario:
            raise NotFoundError("Usuario no encontrado")

        if autorizado_por is not None:
            self._administrador_autorizado(autorizado_por)
            if normalizar_rut(autorizado_por) == rut_norm:
                raise AuthorizationError(
                    "No puedes desactivar tu propia cuenta. Otro administrador debe hacerlo."
                )

        if usuario.get("activo", False) and usuario.get("rol") == "Administrador":
            administradores = self.repo.get_by_rol("Administrador")
            activos = [admin for admin in administradores if admin.get("activo", False)]
            if len(activos) <= 1:
                raise AuthorizationError(
                    "Debe quedar al menos un administrador activo en el sistema."
                )

        if not usuario.get("activo", False):
            return usuario
        return self.repo.deactivate("rut_usuario", rut_norm)

    def _administrador_autorizado(self, rut: str) -> Dict:
        """Devuelve el administrador activo o rechaza la operación."""
        try:
            rut_norm = normalizar_rut(rut)
        except InvalidRUTError:
            raise AuthorizationError(
                "Solo administradores autorizados pueden gestionar usuarios"
            )
        autorizador = self.repo.get_by_rut(rut_norm)
        if (
            not autorizador
            or not autorizador.get("activo")
            or autorizador.get("rol") != "Administrador"
        ):
            raise AuthorizationError(
                "Solo administradores autorizados pueden gestionar usuarios"
            )
        return autorizador
    
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
        return self.activar_usuario(rut, autorizado_por=autorizar_por)
