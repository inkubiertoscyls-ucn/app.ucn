"""Lecturas y administración de proveedores.

Solo administradores pueden listar el catálogo completo o modificarlo.
No existe relación proveedor–producto en el esquema; esta capa no la inventa.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from data.cache import cache_datos, limpiar_cache
from data.errors import como_error
from data.permisos import exigir_admin
from services.proveedores import ProveedoresService


@cache_datos(ttl=60)
def _proveedores() -> List[Dict]:
    try:
        return ProveedoresService().listar_proveedores(solo_activos=False)
    except Exception as exc:
        raise como_error(exc) from exc


def listar_proveedores_admin(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Lista proveedores activos e inactivos. Exclusivo de administradores."""
    exigir_admin(usuario)
    return _proveedores()


def _ejecutar_escritura(accion) -> Dict:
    try:
        resultado = accion()
    except Exception as exc:
        raise como_error(exc) from exc
    limpiar_cache()
    return resultado


def registrar_proveedor(
    data: Dict[str, Any],
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Registra un proveedor. Solo administradores."""
    exigir_admin(usuario)
    return _ejecutar_escritura(
        lambda: ProveedoresService().registrar_proveedor(data)
    )


def modificar_proveedor(
    rut: str,
    data: Dict[str, Any],
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Modifica un proveedor. Solo administradores; el RUT es inmutable."""
    exigir_admin(usuario)
    return _ejecutar_escritura(
        lambda: ProveedoresService().modificar_proveedor(rut, data)
    )


def cambiar_estado_proveedor(
    rut: str,
    activo: bool,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Activa o desactiva un proveedor sin borrar su historial."""
    exigir_admin(usuario)
    servicio = ProveedoresService()
    if activo:
        return _ejecutar_escritura(lambda: servicio.activar_proveedor(rut))
    return _ejecutar_escritura(lambda: servicio.desactivar_proveedor(rut))
