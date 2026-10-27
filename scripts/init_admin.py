#!/usr/bin/env python
"""
Script de inicialización del primer administrador.
Ejecutar localmente desde VS Code/terminal. NO exponer en producción web.
"""
import sys
import getpass
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.usuarios import UsuariosService
from repositories.usuarios import UsuariosRepository
from core.utils import normalizar_rut, validar_rut
from core.auth_password import hash_password


def init_first_admin():
    """Initialize first admin user if none exists."""
    print("=" * 50)
    print("INICIALIZACIÓN DEL PRIMER ADMINISTRADOR - INKubiertos")
    print("=" * 50)
    print()
    
    usuarios_repo = UsuariosRepository()
    usuarios_service = UsuariosService()
    
    # Check if any administrator exists
    try:
        admins = usuarios_repo.get_by_rol("Administrador")
        if admins and len(admins) > 0:
            print("⚠️  Ya existe al menos un administrador.")
            print(f"   Administradores encontrados: {len(admins)}")
            print("   Este script se detendrá para no crear cuentas privilegiadas repetidas.")
            return
    except Exception as e:
        print(f"❌ Error al verificar administradores: {e}")
        return
    
    print("No se encontraron administradores.")
    print("Procediendo a crear el primer administrador...")
    print()
    
    # Get RUT
    rut = input("RUT del administrador (con dígito verificador): ").strip()
    try:
        rut_norm = normalizar_rut(rut)
        if not validar_rut(rut_norm):
            print("❌ RUT inválido")
            return
        print(f"RUT normalizado: {rut_norm}")
    except Exception as e:
        print(f"❌ RUT inválido: {e}")
        return
    
    # Check if user exists
    try:
        existing = usuarios_repo.get_by_rut(rut_norm)
        if existing:
            print("⚠️  Ya existe un usuario con este RUT.")
            print("   No se puede crear como primer administrador. Use el proceso normal de autorización.")
            return
    except Exception as e:
        print(f"❌ Error al verificar usuario: {e}")
        return
    
    # Get name
    nombre = input("Nombre completo: ").strip()
    if not nombre:
        print("❌ Nombre requerido")
        return
    
    # Get password securely
    print()
    print("La contraseña debe tener al menos 8 caracteres.")
    password = getpass.getpass("Contraseña: ")
    password_confirm = getpass.getpass("Confirmar contraseña: ")
    
    if password != password_confirm:
        print("❌ Las contraseñas no coinciden")
        return
    if len(password) < 8:
        print("❌ La contraseña debe tener al menos 8 caracteres")
        return
    
    # Create admin using bootstrap method
    try:
        data = {
            "rut_usuario": rut_norm,
            "nombre_usuario": nombre,
            "password": password
        }
        usuario = usuarios_service.crear_primer_administrador(data)
        print()
        print("✅ Primer administrador creado exitosamente")
        print(f"   RUT: {usuario.get('rut_usuario')}")
        print(f"   Nombre: {usuario.get('nombre_usuario')}")
        print(f"   Rol: {usuario.get('rol')}")
        print(f"   Activo: {usuario.get('activo')}")
        print("   Contraseña: [NO ALMACENADA - solo hash Argon2id guardado]")
    except Exception as e:
        print(f"❌ Error al crear administrador: {e}")
        return
    
    print()
    print("=" * 50)
    print("Inicialización completada")
    print("=" * 50)


if __name__ == "__main__":
    try:
        init_first_admin()
    except KeyboardInterrupt:
        print("\n\nOperación cancelada")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
