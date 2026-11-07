"""Lecturas y administración del catálogo de productos."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from data.cache import cache_datos, limpiar_cache
from data.errors import como_error
from data.permisos import exigir_admin
from repositories.productos import ProductosRepository
from services.productos import ProductosService


@cache_datos(ttl=60)
def _productos(solo_activos: bool) -> List[Dict]:
    try:
        return ProductosService().listar_productos(solo_activos=solo_activos)
    except Exception as exc:
        raise como_error(exc) from exc


def listar_productos(solo_activos: bool = True) -> List[Dict]:
    """Lista productos; por defecto solo los activos."""
    return _productos(bool(solo_activos))


@cache_datos(ttl=60)
def _buscar(termino: str) -> List[Dict]:
    try:
        return ProductosRepository().buscar_estricto(termino)
    except Exception as exc:
        raise como_error(exc) from exc


def buscar_productos(termino: str, solo_activos: bool = True) -> List[Dict]:
    """Busca por nombre o categoría.

    Se mantiene la regla existente de mínimo dos caracteres. Un término muy
    corto devuelve una lista vacía, no un error.
    """
    texto = (termino or "").strip()
    if len(texto) < 2:
        return []

    resultados = _buscar(texto)
    if solo_activos:
        resultados = [fila for fila in resultados if fila.get("activo", True)]
    return resultados


def listar_productos_admin(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Lista el catálogo completo, incluidos los inactivos.

    Es una lectura de administración: exige rol Administrador en la capa de
    datos, no solo en la vista.
    """
    exigir_admin(usuario)
    return _productos(False)


def _ejecutar_escritura(accion) -> Dict:
    """Ejecuta una escritura, traduce el error e invalida la caché."""
    try:
        resultado = accion()
    except Exception as exc:
        raise como_error(exc) from exc
    limpiar_cache()
    return resultado


def registrar_producto(
    data: Dict[str, Any],
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Registra un producto. Solo administradores; no crea stock."""
    exigir_admin(usuario)
    return _ejecutar_escritura(lambda: ProductosService().registrar_producto(data))


def modificar_producto(
    id_producto: int,
    data: Dict[str, Any],
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Modifica un producto. Solo administradores; no crea stock."""
    exigir_admin(usuario)
    return _ejecutar_escritura(
        lambda: ProductosService().modificar_producto(id_producto, data)
    )


def cambiar_estado_producto(
    id_producto: int,
    activo: bool,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Activa o desactiva un producto sin borrar su historial."""
    exigir_admin(usuario)
    servicio = ProductosService()
    if activo:
        return _ejecutar_escritura(lambda: servicio.activar_producto(id_producto))
    return _ejecutar_escritura(lambda: servicio.desactivar_producto(id_producto))
