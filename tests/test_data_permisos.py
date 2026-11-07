"""Pruebas de los guards de permisos de la capa de datos."""
import pytest

from core.exceptions import AuthorizationError
from data.permisos import area_operario, exigir_admin, exigir_sesion, es_admin

ADMIN = {
    "rut_usuario": "12345678-9",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
}
OPERARIO = {
    "rut_usuario": "11111111-1",
    "rol": "Operario",
    "area_asignada": "Barra",
    "activo": True,
}
OPERARIO_INACTIVO = {**OPERARIO, "activo": False}
OPERARIO_SIN_AREA = {**OPERARIO, "area_asignada": ""}


def test_admin_puede_entrar():
    assert exigir_admin(ADMIN) == ADMIN
    assert es_admin(ADMIN) is True


def test_operario_no_puede_entrar_a_administracion():
    with pytest.raises(AuthorizationError):
        exigir_admin(OPERARIO)


def test_usuario_inactivo_es_rechazado():
    with pytest.raises(AuthorizationError):
        exigir_sesion(OPERARIO_INACTIVO)


def test_sin_sesion_es_rechazado():
    with pytest.raises(AuthorizationError):
        exigir_sesion({})


def test_area_operario_es_su_area():
    assert area_operario(OPERARIO) == "Barra"


def test_admin_no_tiene_area_fija():
    assert area_operario(ADMIN) is None


def test_operario_sin_area_valida_es_rechazado():
    with pytest.raises(AuthorizationError):
        area_operario(OPERARIO_SIN_AREA)
