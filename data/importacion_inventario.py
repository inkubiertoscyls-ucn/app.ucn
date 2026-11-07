"""Capa de datos de la importación de movimientos de inventario.

Valida la sesión (Administrador u Operario) y el archivo antes de delegar en
el servicio. Ninguna función escribe en Supabase durante la vista previa: la
escritura solo ocurre en `importar_entradas_inventario` con confirmación
explícita.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from data.cache import limpiar_cache
from data.errors import VALIDACION, ErrorDatos, como_error
from data.permisos import exigir_sesion
from services.importacion_inventario import ImportacionInventarioService

logger = logging.getLogger(__name__)

EXTENSION = ".xlsx"
TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024
ROLES_IMPORTACION = ("Administrador", "Operario")


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
        return "movimientos_inventario.xlsx"
    nombre_base = Path(texto.replace("\\", "/")).name
    if not nombre_base.lower().endswith(EXTENSION):
        nombre_base = f"{nombre_base}{EXTENSION}"
    return nombre_base


def _validar_archivo(contenido: Any, nombre: Any) -> bytes:
    datos = _contenido_bytes(contenido)
    nombre_original = str(nombre or "").replace("\\", "/")
    if Path(nombre_original).suffix.lower() != EXTENSION:
        raise ErrorDatos(
            "Formato no soportado. Carga un archivo Excel .xlsx.",
            tipo=VALIDACION,
        )
    if not datos:
        raise ErrorDatos(
            "El archivo está vacío. Selecciona un archivo con datos.",
            tipo=VALIDACION,
        )
    if len(datos) > TAMANO_MAXIMO_BYTES:
        raise ErrorDatos(
            "El archivo supera el tamaño máximo permitido de 10 MB.",
            tipo=VALIDACION,
        )
    return datos


def _servicio() -> ImportacionInventarioService:
    return ImportacionInventarioService()


def _exigir_importador(
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Exige una sesión activa con rol autorizado para importar."""
    actual = exigir_sesion(usuario)
    if actual.get("rol") not in ROLES_IMPORTACION:
        raise ErrorDatos(
            "Tu perfil no tiene permisos para importar movimientos.",
            tipo=VALIDACION,
        )
    return actual


def _rut_sesion(usuario: Dict[str, Any]) -> str:
    rut = str(usuario.get("rut_usuario") or "").strip()
    if not rut:
        raise ErrorDatos(
            "Tu sesión no tiene un usuario válido. Vuelve a iniciar sesión.",
            tipo=VALIDACION,
        )
    return rut


def generar_plantilla_inventario(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Genera la plantilla descargable. No escribe en Supabase."""
    _exigir_importador(usuario)
    try:
        return _servicio().generar_plantilla()
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc


def previsualizar_importacion_inventario(
    contenido: Any,
    nombre: Any,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Lee y valida el archivo completo sin escribir nada."""
    actual = _exigir_importador(usuario)
    datos = _validar_archivo(contenido, nombre)
    try:
        return _servicio().analizar(
            datos,
            _nombre_limpio(nombre),
            usuario_rut=_rut_sesion(actual),
        )
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc


def importar_entradas_inventario(
    contenido: Any,
    nombre: Any,
    *,
    confirmado: bool = False,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Importa las filas válidas después de la confirmación explícita."""
    actual = _exigir_importador(usuario)
    if not confirmado:
        raise ErrorDatos(
            "Debes confirmar explícitamente la importación antes de continuar.",
            tipo=VALIDACION,
        )

    rut = _rut_sesion(actual)
    datos = _validar_archivo(contenido, nombre)
    try:
        resultado = _servicio().importar(
            datos,
            _nombre_limpio(nombre),
            rut,
            confirmado=True,
        )
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc

    limpiar_cache()
    return resultado
