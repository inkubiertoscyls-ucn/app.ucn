"""Pruebas de las lecturas de usuarios y protección de datos sensibles."""
import pytest

from core.exceptions import AuthorizationError, SupabaseConnectionError
from data.errors import CONEXION, ErrorDatos
from data.usuarios import listar_usuarios

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


class FakeUsuariosService:
    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.solo_activos = None

    def listar_usuarios(self, solo_activos=False):
        self.solo_activos = solo_activos
        if self.error:
            raise self.error
        return self.filas


def test_elimina_password_hash(monkeypatch):
    servicio = FakeUsuariosService(
        [
            {
                "rut_usuario": "11111111-1",
                "nombre_usuario": "Operario",
                "rol": "Operario",
                "area_asignada": "Barra",
                "activo": True,
                "password_hash": "$argon2id$secreto",
            }
        ]
    )
    monkeypatch.setattr("data.usuarios.UsuariosService", lambda: servicio)

    usuarios = listar_usuarios(usuario=ADMIN)

    assert usuarios == [
        {
            "rut_usuario": "11111111-1",
            "nombre_usuario": "Operario",
            "rol": "Operario",
            "area_asignada": "Barra",
            "activo": True,
        }
    ]
    assert "password_hash" not in usuarios[0]


def test_operario_no_puede_listar_usuarios(monkeypatch):
    monkeypatch.setattr("data.usuarios.UsuariosService", lambda: FakeUsuariosService())

    with pytest.raises(AuthorizationError):
        listar_usuarios(usuario=OPERARIO)


def test_pasa_filtro_solo_activos(monkeypatch):
    servicio = FakeUsuariosService([])
    monkeypatch.setattr("data.usuarios.UsuariosService", lambda: servicio)

    listar_usuarios(solo_activos=True, usuario=ADMIN)

    assert servicio.solo_activos is True


def test_error_de_conexion_se_traduce(monkeypatch):
    servicio = FakeUsuariosService(error=SupabaseConnectionError("sin red"))
    monkeypatch.setattr("data.usuarios.UsuariosService", lambda: servicio)

    with pytest.raises(ErrorDatos) as info:
        listar_usuarios(usuario=ADMIN)

    assert info.value.tipo == CONEXION
