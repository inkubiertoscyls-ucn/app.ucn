"""Pruebas de la traducción de errores de la capa de datos."""
import httpx
import pytest

from core.exceptions import (
    AuthorizationError,
    NegativeStockError,
    SupabaseConnectionError,
    ValidationError,
)
from data.errors import (
    CONEXION,
    DESCONOCIDO,
    ESQUEMA,
    INTERNO,
    PERMISOS,
    VALIDACION,
    ErrorDatos,
    como_error,
    texto_error,
)


def test_conexion_supabase():
    error = como_error(SupabaseConnectionError("fallo interno"))
    assert error.tipo == CONEXION
    assert "conectar" in error.mensaje.lower()


def test_conexion_httpx():
    error = como_error(httpx.ConnectError("connection refused"))
    assert error.tipo == CONEXION


def test_permisos_conserva_mensaje_de_negocio():
    error = como_error(AuthorizationError("Esta sección es exclusiva para administradores."))
    assert error.tipo == PERMISOS
    assert error.mensaje == "Esta sección es exclusiva para administradores."


def test_validacion_conserva_mensaje():
    error = como_error(ValidationError("La cantidad debe ser positiva"))
    assert error.tipo == VALIDACION
    assert error.mensaje == "La cantidad debe ser positiva"


def test_stock_negativo_conserva_mensaje_de_inventario():
    error = como_error(NegativeStockError("Stock insuficiente. Actual: 3"))
    assert error.tipo == VALIDACION
    assert error.mensaje == "Stock insuficiente. Actual: 3"


def test_error_de_esquema_pgrst200():
    exc = Exception('{"code":"PGRST200","message":"Could not find a relationship"}')
    error = como_error(exc)
    assert error.tipo == ESQUEMA
    assert error.codigo == "PGRST200"


def test_error_de_permisos_postgrest():
    error = como_error(Exception('{"code":"42501","message":"permission denied"}'))
    assert error.tipo == PERMISOS


def test_error_desconocido_no_expone_detalle():
    error = como_error(RuntimeError("postgres://usuario:clave@host/base"))
    assert error.tipo == DESCONOCIDO
    assert "postgres://" not in str(error)
    assert "clave" not in str(error)
    assert texto_error(RuntimeError("conexión rota")) == error.mensaje


def test_error_datos_se_devuelve_igual():
    original = ErrorDatos("mensaje propio", tipo=VALIDACION)
    assert como_error(original) is original


def test_error_de_renderizado_es_interno_y_no_conexion():
    error = como_error(
        TypeError("metric_grid() got an unexpected keyword argument 'columns'")
    )
    assert error.tipo == INTERNO
    assert "conectar" not in error.mensaje.lower()
    assert "conexión" not in error.mensaje.lower()


def test_columna_obligatoria_faltante_menciona_el_campo():
    exc = Exception(
        '{"code":"23502","message":"null value in column '
        '\\"costo_unitario\\" of relation \\"hecho_inventario\\" violates '
        'not-null constraint"}'
    )

    error = como_error(exc)

    assert error.tipo == VALIDACION
    assert error.codigo == "23502"
    assert "costo unitario" in error.mensaje.lower()
    assert "hecho_inventario" not in error.mensaje


def test_check_de_tipo_evento_tiene_mensaje_especifico():
    exc = Exception(
        '{"code":"23514","message":"new row for relation \\"dim_evento\\" '
        'violates check constraint '
        '\\"dim_evento_tipo_evento_check\\""}'
    )

    error = como_error(exc)

    assert error.tipo == VALIDACION
    assert "tipo de evento" in error.mensaje.lower()
    assert "Concierto" in error.mensaje


def test_texto_demasiado_largo_indica_el_limite():
    exc = Exception(
        '{"code":"22001","message":"value too long for type '
        'character varying(50)"}'
    )

    error = como_error(exc)

    assert error.tipo == VALIDACION
    assert "demasiado largo" in error.mensaje.lower()
    assert "50" in error.mensaje


def test_formato_invalido_menciona_el_campo():
    exc = Exception(
        '{"code":"22P02","message":"invalid input syntax for type integer: '
        '\\"abc\\""}'
    )

    error = como_error(exc)

    assert error.tipo == VALIDACION
    assert "formato" in error.mensaje.lower()
    assert "abc" not in error.mensaje
