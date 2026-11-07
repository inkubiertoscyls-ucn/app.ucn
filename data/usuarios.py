"""Lecturas y cambios de estado de usuarios para administración.

Solo administradores pueden listar, activar o desactivar cuentas y nunca se
devuelve `password_hash` a la interfaz.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from data.cache import cache_datos, limpiar_cache
from data.errors import como_error
from data.permisos import exigir_admin
from services.usuarios import UsuariosService

CAMPOS_VISIBLES = (
    "rut_usuario",
    "nombre_usuario",
    "rol",
    "area_asignada",
    "activo",
    "fecha_creacion",
)


def _sanitizar(usuario: Dict[str, Any]) -> Dict[str, Any]:
    return {campo: usuario.get(campo) for campo in CAMPOS_VISIBLES if campo in usuario}


@cache_datos(ttl=60)
def _usuarios(solo_activos: bool) -> List[Dict]:
    try:
        usuarios = UsuariosService().listar_usuarios(solo_activos=solo_activos)
    except Exception as exc:
        raise como_error(exc) from exc
    return [_sanitizar(usuario) for usuario in usuarios]


def listar_usuarios(
    solo_activos: bool = False,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Lista usuarios sin datos sensibles. Exclusivo de administradores."""
    exigir_admin(usuario)
    return _usuarios(bool(solo_activos))


def _cambiar_estado(
    rut: str,
    activo: bool,
    usuario: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Activa o desactiva una cuenta exigiendo un administrador de sesión."""
    actual = exigir_admin(usuario)
    servicio = UsuariosService()
    try:
        if activo:
            resultado = servicio.activar_usuario(
                rut,
                autorizado_por=actual.get("rut_usuario"),
            )
        else:
            resultado = servicio.desactivar_usuario(
                rut,
                autorizado_por=actual.get("rut_usuario"),
            )
    except Exception as exc:
        raise como_error(exc) from exc

    # El listado cacheado debe reflejar el nuevo estado de inmediato.
    limpiar_cache()
    return _sanitizar(resultado)


def activar_usuario(
    rut: str,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Activa una cuenta. Solo administradores; nunca expone `password_hash`."""
    return _cambiar_estado(rut, True, usuario)


def desactivar_usuario(
    rut: str,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Desactiva una cuenta sin borrar su historial.

    Solo administradores. La auto-desactivación y la desactivación del último
    administrador activo se rechazan también en la capa de servicio.
    """
    return _cambiar_estado(rut, False, usuario)
