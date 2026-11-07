"""Traducción de errores de datos a mensajes claros en español.

La capa de datos nunca muestra credenciales ni detalles técnicos en pantalla.
El detalle interno se registra solo con el tipo de excepción y el código.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from core.exceptions import (
    AuthorizationError,
    DuplicateError,
    InventoryError,
    NotFoundError,
    SupabaseConnectionError,
    ValidationError,
)

logger = logging.getLogger(__name__)

CONEXION = "conexion"
PERMISOS = "permisos"
VALIDACION = "validacion"
NO_ENCONTRADO = "no_encontrado"
DUPLICADO = "duplicado"
ESQUEMA = "esquema"
INTERNO = "interno"
DESCONOCIDO = "desconocido"

MENSAJES = {
    CONEXION: "No se pudo conectar con la base de datos. Revisa tu conexión e intenta nuevamente.",
    PERMISOS: "No tienes permisos para realizar esta acción.",
    VALIDACION: "Los datos ingresados no son válidos.",
    NO_ENCONTRADO: "No se encontró la información solicitada.",
    DUPLICADO: "El registro ya existe.",
    ESQUEMA: "La estructura de datos no está disponible en este momento. Contacta al administrador.",
    INTERNO: "Ocurrió un error interno en la pantalla. Contacta al administrador.",
    DESCONOCIDO: "No se pudieron cargar los datos. Intenta nuevamente en unos minutos.",
}

# Errores de programación o de renderizado: nunca son problemas de conexión.
_ERRORES_INTERNOS = (
    TypeError,
    AttributeError,
    NameError,
    KeyError,
    IndexError,
    AssertionError,
)

_CODIGOS_CONEXION = {"08000", "08003", "08006"}
_CODIGOS_ESQUEMA = {"42P01", "PGRST116", "PGRST200", "PGRST204", "PGRST205"}
_CODIGOS_PERMISOS = {"42501", "PGRST301"}
_CODIGOS_DUPLICADO = {"23505"}
_CODIGOS_VALIDACION = {"23502", "23503", "23514", "22001", "22P02"}

# Solo se exponen nombres de columna/restricción saneados. Nunca el mensaje
# crudo de PostgreSQL, que puede incluir valores sensibles de las filas.
_IDENTIFICADOR = re.compile(r"^[A-Za-z0-9_.]{1,64}$")
_COLUMNA = re.compile(r'column\s+\\?"?([A-Za-z0-9_.]{1,64})', re.IGNORECASE)
_RESTRICCION = re.compile(
    r'constraint\s+\\?"?([A-Za-z0-9_.]{1,64})', re.IGNORECASE
)
_LONGITUD = re.compile(
    r"character varying\((\d{1,6})\)", re.IGNORECASE
)

_ETIQUETAS_CAMPO = {
    "costo_unitario": "costo unitario",
    "id_fecha": "fecha",
    "id_producto": "producto",
    "id_area": "área",
    "id_tipo_movimiento": "tipo de movimiento",
    "rut_usuario": "usuario",
    "rut_proveedor": "proveedor",
    "id_evento": "evento",
    "cantidad": "cantidad",
    "observacion": "observación",
    "fecha_hora_registro": "fecha y hora de registro",
    "nombre_evento": "nombre del evento",
    "nombre_artista": "artista",
    "tipo_evento": "tipo de evento",
    "costo_artista": "costo del artista",
}

_MENSAJES_REFERENCIA = {
    "producto": "El producto seleccionado ya no existe o no está disponible.",
    "área": "El área seleccionada ya no existe o no está disponible.",
    "tipo de movimiento": (
        "El tipo de movimiento seleccionado ya no existe o no está disponible."
    ),
    "usuario": "El usuario indicado ya no existe o no está disponible.",
    "proveedor": "El proveedor indicado ya no existe o no está disponible.",
    "evento": "El evento indicado ya no existe o no está disponible.",
}


def _campo_saneado(exc: BaseException) -> str:
    """Extrae el nombre de columna de PostgreSQL sin exponer valores."""
    coincidencia = _COLUMNA.search(str(exc))
    if not coincidencia:
        return ""
    nombre = coincidencia.group(1).split(".")[-1]
    return nombre if _IDENTIFICADOR.match(nombre) else ""


def _restriccion_saneada(exc: BaseException) -> str:
    """Extrae el nombre de la restricción, validando su formato."""
    coincidencia = _RESTRICCION.search(str(exc))
    if not coincidencia:
        return ""
    nombre = coincidencia.group(1).split(".")[-1]
    return nombre if _IDENTIFICADOR.match(nombre) else ""


def _etiqueta(campo: str) -> str:
    return _ETIQUETAS_CAMPO.get(campo, campo.replace("_", " "))


def _mensaje_postgres(exc: BaseException, codigo: str) -> Optional[str]:
    """Traduce errores de integridad a mensajes accionables y sin datos crudos.

    Solo usa el código, el nombre de la columna/restricción y la longitud
    declarada por el tipo. No copia el mensaje del proveedor ni los valores.
    """
    if codigo not in _CODIGOS_VALIDACION:
        return None

    campo = _campo_saneado(exc)
    restriccion = _restriccion_saneada(exc)
    etiqueta = _etiqueta(campo) if campo else ""
    referencia = f"{campo} {restriccion}".lower()

    if codigo == "23502":
        if etiqueta:
            return f"Falta completar el campo obligatorio: {etiqueta}."
        return "Falta completar un dato obligatorio para guardar el registro."

    if codigo == "23503":
        if etiqueta in _MENSAJES_REFERENCIA:
            return _MENSAJES_REFERENCIA[etiqueta]
        for clave, mensaje in _MENSAJES_REFERENCIA.items():
            if clave in referencia:
                return mensaje
        return (
            "El registro hace referencia a un dato que no existe o ya no está "
            "disponible. Revisa la selección e intenta nuevamente."
        )

    if codigo == "23514":
        if "tipo_evento" in referencia or etiqueta == "tipo de evento":
            return (
                "El tipo de evento no es válido. Usa una de las opciones "
                "permitidas (por ejemplo: Concierto, Festival o Privado) o "
                "revisa el catálogo antes de guardar."
            )
        if etiqueta:
            return (
                f"El valor de {etiqueta} no cumple una regla de la base de "
                "datos. Revisa el dato e intenta nuevamente."
            )
        return (
            "Uno de los valores ingresados no cumple una regla de la base de "
            "datos. Revisa el formulario e intenta nuevamente."
        )

    if codigo == "22001":
        longitud = _LONGITUD.search(str(exc))
        limite = f" Máximo: {longitud.group(1)} caracteres." if longitud else ""
        if etiqueta:
            return f"El texto ingresado es demasiado largo para {etiqueta}.{limite}"
        return f"Uno de los textos ingresados es demasiado largo.{limite}"

    if codigo == "22P02":
        if etiqueta:
            return f"El formato de {etiqueta} no es válido. Revisa el dato ingresado."
        return (
            "Uno de los valores ingresados tiene un formato que no corresponde. "
            "Revisa fechas, cantidades y números."
        )

    return None


def _registro_seguro(exc: BaseException, codigo: str) -> str:
    """Arma el detalle de log sin URL, credenciales ni valores de fila."""
    partes = [f"codigo={codigo or '-'}"]
    campo = _campo_saneado(exc)
    restriccion = _restriccion_saneada(exc)
    if campo:
        partes.append(f"campo={campo}")
    if restriccion:
        partes.append(f"restriccion={restriccion}")
    return " ".join(partes)


class ErrorDatos(Exception):
    """Error de lectura con un mensaje apto para mostrar al usuario."""

    def __init__(
        self,
        mensaje: str,
        *,
        tipo: str = DESCONOCIDO,
        codigo: str = "",
        causa: Optional[BaseException] = None,
    ) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.tipo = tipo
        self.codigo = codigo
        self.causa = causa

    def __str__(self) -> str:
        return self.mensaje


def _codigo(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    texto = str(exc)
    for candidato in (
        "PGRST200",
        "PGRST116",
        "PGRST204",
        "PGRST301",
        "42P01",
        "42501",
        "23505",
        "23503",
        "23514",
        "23502",
        "22001",
        "22P02",
    ):
        if candidato in texto:
            return candidato
    return ""


def _mensaje_de(exc: BaseException, tipo: str) -> str:
    """Usa el mensaje propio cuando es seguro y conocido."""
    if isinstance(exc, (AuthorizationError, ValidationError, NotFoundError, DuplicateError, InventoryError)):
        texto = str(exc).strip()
        if texto:
            return texto
    return MENSAJES.get(tipo, MENSAJES[DESCONOCIDO])


def como_error(exc: BaseException) -> ErrorDatos:
    """Convierte cualquier excepción en un ErrorDatos con mensaje en español."""
    if isinstance(exc, ErrorDatos):
        return exc

    codigo = _codigo(exc)
    texto = str(exc).lower()

    if isinstance(exc, SupabaseConnectionError):
        tipo = CONEXION
    elif isinstance(exc, (httpx.TransportError, httpx.TimeoutException, ConnectionError, TimeoutError, OSError)):
        tipo = CONEXION
    elif isinstance(exc, AuthorizationError):
        tipo = PERMISOS
    elif isinstance(exc, ValidationError):
        tipo = VALIDACION
    elif isinstance(exc, NotFoundError):
        tipo = NO_ENCONTRADO
    elif isinstance(exc, DuplicateError):
        tipo = DUPLICADO
    elif isinstance(exc, InventoryError):
        tipo = VALIDACION
    elif codigo in _CODIGOS_CONEXION:
        tipo = CONEXION
    elif codigo in _CODIGOS_PERMISOS or "permission denied" in texto or "row-level security" in texto:
        tipo = PERMISOS
    elif codigo in _CODIGOS_ESQUEMA or "schema cache" in texto or "does not exist" in texto:
        tipo = ESQUEMA
    elif codigo in _CODIGOS_DUPLICADO:
        tipo = DUPLICADO
    elif codigo in _CODIGOS_VALIDACION:
        tipo = VALIDACION
    elif isinstance(exc, _ERRORES_INTERNOS):
        tipo = INTERNO
    else:
        tipo = DESCONOCIDO

    # Nunca se registra la URL, la clave ni el mensaje crudo del proveedor.
    logger.error(
        "Error de datos (%s, %s): %s",
        tipo,
        _registro_seguro(exc, codigo),
        type(exc).__name__,
    )

    mensaje = None
    if not isinstance(
        exc,
        (
            AuthorizationError,
            ValidationError,
            NotFoundError,
            DuplicateError,
            InventoryError,
        ),
    ):
        mensaje = _mensaje_postgres(exc, codigo)
    mensaje = mensaje or _mensaje_de(exc, tipo)

    return ErrorDatos(
        mensaje,
        tipo=tipo,
        codigo=codigo,
        causa=exc,
    )


def texto_error(exc: BaseException) -> str:
    """Atajo para obtener solo el mensaje de usuario."""
    return como_error(exc).mensaje
