"""Lecturas de catálogos: áreas, tipos de movimiento, proveedores y eventos."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.areas import resolver_area_id
from data.cache import cache_datos
from data.errors import como_error
from repositories.base import BaseRepository


def _ordenar(filas: List[Dict], campo: str) -> List[Dict]:
    return sorted(filas, key=lambda fila: str(fila.get(campo) or "").lower())


@cache_datos(ttl=300)
def _areas(incluir_inactivas: bool) -> List[Dict]:
    filtros = None if incluir_inactivas else {"activo": True}
    try:
        filas = BaseRepository("dim_area").get_all(filtros)
    except Exception as exc:
        raise como_error(exc) from exc
    return _ordenar(filas, "nombre_area")


def listar_areas(incluir_inactivas: bool = False) -> List[Dict]:
    """Áreas del catálogo, activas por defecto."""
    return _areas(bool(incluir_inactivas))


def area_id(valor: Any, areas: Optional[List[Dict]] = None) -> Optional[int]:
    """Convierte un nombre de área al id activo del catálogo."""
    catalogo = areas if areas is not None else listar_areas()
    return resolver_area_id(valor, catalogo)


@cache_datos(ttl=300)
def _tipos_movimiento(incluir_inactivos: bool) -> List[Dict]:
    filtros = None if incluir_inactivos else {"activo": True}
    try:
        filas = BaseRepository("dim_tipo_movimiento").get_all(filtros)
    except Exception as exc:
        raise como_error(exc) from exc
    return sorted(filas, key=lambda fila: int(fila.get("id_tipo_movimiento") or 0))


def listar_tipos_movimiento(incluir_inactivos: bool = False) -> List[Dict]:
    """Tipos de movimiento, activos por defecto, incluido su factor de stock."""
    return _tipos_movimiento(bool(incluir_inactivos))


@cache_datos(ttl=300)
def _proveedores() -> List[Dict]:
    try:
        filas = BaseRepository("dim_proveedor").get_all({"activo": True})
    except Exception as exc:
        raise como_error(exc) from exc
    return _ordenar(filas, "nombre_proveedor")


def listar_proveedores() -> List[Dict]:
    """Proveedores activos."""
    return _proveedores()


@cache_datos(ttl=300)
def _eventos(incluir_inactivos: bool) -> List[Dict]:
    filtros = None if incluir_inactivos else {"activo": True}
    try:
        filas = BaseRepository("dim_evento").get_all(filtros)
    except Exception as exc:
        raise como_error(exc) from exc
    return _ordenar(filas, "nombre_evento")


def listar_eventos(incluir_inactivos: bool = False) -> List[Dict]:
    """Eventos del catálogo.

    Por defecto solo activos. Los consumidores históricos deben pedir
    `incluir_inactivos=True` para conservar las etiquetas de eventos ya
    referenciados en ventas o movimientos.
    """
    return _eventos(bool(incluir_inactivos))
