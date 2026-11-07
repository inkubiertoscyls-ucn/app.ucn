"""Capa de datos de la importación FUDO.

Gestiona el archivo temporal con limpieza garantizada, valida permisos de
administrador y expone la inspección, la vista previa y la confirmación de la
importación. Ninguna función vincula productos ni eventos automáticamente.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterator, Optional, Tuple

from core.exceptions import ValidationError
from data.cache import limpiar_cache
from data.errors import VALIDACION, ErrorDatos, como_error
from data.permisos import exigir_admin
from repositories.ventas import VentasFudoRepository
from services.fudo_import import (
    EXTENSIONES_PERMITIDAS,
    FudoImportService,
)

logger = logging.getLogger(__name__)

TAMANO_MAXIMO_BYTES = 25 * 1024 * 1024


def _contenido_bytes(contenido: Any) -> bytes:
    if isinstance(contenido, bytes):
        return contenido
    if isinstance(contenido, (bytearray, memoryview)):
        return bytes(contenido)
    raise ErrorDatos(
        "No se pudo leer el archivo seleccionado.",
        tipo=VALIDACION,
    )


def _nombre_limpio(nombre: Any) -> str:
    texto = str(nombre or "").strip()
    if not texto:
        return "archivo_fudo"
    nombre_base = Path(texto.replace("\\", "/")).name
    # `origen_archivo` es VARCHAR(255); se recorta conservando la extensión.
    if len(nombre_base) > 255:
        extension = Path(nombre_base).suffix
        nombre_base = nombre_base[: 255 - len(extension)] + extension
    return nombre_base


@contextmanager
def archivo_temporal(
    contenido: Any,
    nombre: Any,
) -> Iterator[Tuple[str, str]]:
    """Copia el archivo a un directorio temporal y lo elimina al terminar.

    La extensión se conserva porque el lector de pandas la usa para decidir
    entre CSV y Excel. El `finally` borra el archivo incluso si la lectura o la
    importación fallan, y el directorio temporal se elimina al salir.
    """
    datos = _contenido_bytes(contenido)
    nombre_archivo = _nombre_limpio(nombre)
    extension = Path(nombre_archivo).suffix.lower()

    if extension not in EXTENSIONES_PERMITIDAS:
        raise ErrorDatos(
            "Formato no soportado. Carga un archivo CSV o Excel (.xlsx, .xls).",
            tipo=VALIDACION,
        )
    if not datos:
        raise ErrorDatos(
            "El archivo está vacío. Selecciona un archivo con datos.",
            tipo=VALIDACION,
        )
    if len(datos) > TAMANO_MAXIMO_BYTES:
        raise ErrorDatos(
            "El archivo supera el tamaño máximo permitido de 25 MB.",
            tipo=VALIDACION,
        )

    with TemporaryDirectory(prefix="ink_fudo_") as carpeta:
        ruta = Path(carpeta) / f"archivo{extension}"
        try:
            ruta.write_bytes(datos)
            yield str(ruta), nombre_archivo
        finally:
            try:
                ruta.unlink(missing_ok=True)
            except OSError:
                logger.warning("No se pudo eliminar el archivo temporal FUDO.")


def _servicio() -> FudoImportService:
    return FudoImportService()


def _repo_ventas() -> VentasFudoRepository:
    return VentasFudoRepository()


def inspeccionar_archivo(
    contenido: Any,
    nombre: Any,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Inspecciona hojas, columnas y una muestra del archivo cargado."""
    exigir_admin(usuario)
    try:
        with archivo_temporal(contenido, nombre) as (ruta, nombre_archivo):
            resultado = _servicio().inspeccionar_archivo(ruta)
            resultado["nombre_archivo"] = nombre_archivo
            resultado["tamano_bytes"] = len(_contenido_bytes(contenido))
            return resultado
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc


def previsualizar_importacion(
    contenido: Any,
    nombre: Any,
    *,
    hoja: Optional[str] = None,
    mapeo: Optional[Dict[str, str]] = None,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Valida el archivo completo sin escribir en la base de datos."""
    exigir_admin(usuario)
    try:
        servicio = _servicio()
        mapeo_normalizado = servicio.normalizar_mapeo(mapeo or {})
        hashes = _repo_ventas().hashes_existentes()
        with archivo_temporal(contenido, nombre) as (ruta, nombre_archivo):
            df = servicio.leer_hoja(ruta, hoja)
            resultado = servicio.analizar_dataframe(
                df,
                mapeo_normalizado,
                hashes,
            )
            resultado["nombre_archivo"] = nombre_archivo
            resultado["hoja"] = hoja or ""
            return resultado
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc


def importar_ventas(
    contenido: Any,
    nombre: Any,
    *,
    hoja: Optional[str] = None,
    mapeo: Optional[Dict[str, str]] = None,
    confirmado: bool = False,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Importa las ventas válidas después de una confirmación explícita."""
    actual = exigir_admin(usuario)
    if not confirmado:
        raise ErrorDatos(
            "Debes confirmar explícitamente la importación antes de continuar.",
            tipo=VALIDACION,
        )

    rut = str(actual.get("rut_usuario") or "").strip()
    if not rut:
        raise ErrorDatos(
            "Tu sesión no tiene un usuario válido. Vuelve a iniciar sesión.",
            tipo=VALIDACION,
        )

    try:
        servicio = _servicio()
        mapeo_normalizado = servicio.normalizar_mapeo(mapeo or {})
        hashes = _repo_ventas().hashes_existentes()
        with archivo_temporal(contenido, nombre) as (ruta, nombre_archivo):
            df = servicio.leer_hoja(ruta, hoja)
            resultado = servicio.importar_dataframe(
                df,
                mapeo_normalizado,
                importado_por=rut,
                origen_archivo=nombre_archivo,
                hashes_existentes=hashes,
            )
            resultado["nombre_archivo"] = nombre_archivo
            resultado["hoja"] = hoja or ""
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc

    limpiar_cache()
    return resultado
