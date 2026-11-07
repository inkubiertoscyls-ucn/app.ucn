"""Lecturas y administración del catálogo de eventos y artistas.

Solo administradores pueden consultar el catálogo completo o modificarlo.
El artista se deriva de `dim_evento.nombre_artista`; no se crea una tabla
nueva ni se modifican ventas o movimientos.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from data.cache import cache_datos, limpiar_cache
from data.errors import como_error
from data.permisos import exigir_admin
from services.eventos import EventosService


@cache_datos(ttl=60)
def _eventos() -> List[Dict]:
    try:
        return EventosService().listar_eventos(solo_activos=False)
    except Exception as exc:
        raise como_error(exc) from exc


@cache_datos(ttl=60)
def _actividad() -> Dict[int, Dict[str, str]]:
    try:
        return EventosService().fechas_actividad()
    except Exception as exc:
        raise como_error(exc) from exc


def listar_eventos_admin(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Lista eventos activos e inactivos. Exclusivo de administradores."""
    exigir_admin(usuario)
    return _eventos()


def actividad_eventos_admin(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[int, Dict[str, str]]:
    """Fechas de actividad derivadas. Exclusivo de administradores."""
    exigir_admin(usuario)
    return _actividad()


def _ejecutar_escritura(accion) -> Dict:
    try:
        resultado = accion()
    except Exception as exc:
        raise como_error(exc) from exc
    limpiar_cache()
    return resultado


def registrar_evento(
    data: Dict[str, Any],
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Registra un evento. Solo administradores; no crea movimientos."""
    exigir_admin(usuario)
    return _ejecutar_escritura(lambda: EventosService().registrar_evento(data))


def modificar_evento(
    id_evento: int,
    data: Dict[str, Any],
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Modifica un evento. Solo administradores."""
    exigir_admin(usuario)
    return _ejecutar_escritura(
        lambda: EventosService().modificar_evento(id_evento, data)
    )


def cambiar_estado_evento(
    id_evento: int,
    activo: bool,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Activa o desactiva un evento sin borrar su historial."""
    exigir_admin(usuario)
    servicio = EventosService()
    if activo:
        return _ejecutar_escritura(lambda: servicio.activar_evento(id_evento))
    return _ejecutar_escritura(lambda: servicio.desactivar_evento(id_evento))
