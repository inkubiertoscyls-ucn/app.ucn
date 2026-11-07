"""Pruebas de lectura de catálogos."""
import pytest

from core.exceptions import SupabaseConnectionError
from data.catalogos import area_id, listar_areas, listar_eventos
from data.errors import CONEXION, ErrorDatos


class FakeRepo:
    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.filtros = "sin consultar"

    def get_all(self, filters=None):
        self.filtros = filters
        if self.error:
            raise self.error
        return self.filas


def test_listar_areas_ordena_por_nombre(monkeypatch):
    repo = FakeRepo(
        [
            {"id_area": 2, "nombre_area": "Cocina", "activo": True},
            {"id_area": 1, "nombre_area": "Barra", "activo": True},
        ]
    )
    monkeypatch.setattr("data.catalogos.BaseRepository", lambda tabla: repo)

    areas = listar_areas()

    assert [area["nombre_area"] for area in areas] == ["Barra", "Cocina"]
    assert repo.filtros == {"activo": True}


def test_listar_areas_incluye_inactivas(monkeypatch):
    repo = FakeRepo([{"id_area": 1, "nombre_area": "Barra", "activo": False}])
    monkeypatch.setattr("data.catalogos.BaseRepository", lambda tabla: repo)

    listar_areas(incluir_inactivas=True)

    assert repo.filtros is None


def test_error_de_conexion_se_traduce(monkeypatch):
    repo = FakeRepo(error=SupabaseConnectionError("sin red"))
    monkeypatch.setattr("data.catalogos.BaseRepository", lambda tabla: repo)

    with pytest.raises(ErrorDatos) as info:
        listar_areas()

    assert info.value.tipo == CONEXION


def test_listar_eventos_incluye_inactivos_para_historial(monkeypatch):
    repo = FakeRepo(
        [
            {"id_evento": 2, "nombre_evento": "Zeta", "activo": False},
            {"id_evento": 1, "nombre_evento": "Alfa", "activo": True},
        ]
    )
    monkeypatch.setattr("data.catalogos.BaseRepository", lambda tabla: repo)

    eventos = listar_eventos(incluir_inactivos=True)

    assert [evento["nombre_evento"] for evento in eventos] == ["Alfa", "Zeta"]
    assert repo.filtros is None


def test_listar_eventos_por_defecto_solo_activos(monkeypatch):
    repo = FakeRepo([{"id_evento": 1, "nombre_evento": "Alfa", "activo": True}])
    monkeypatch.setattr("data.catalogos.BaseRepository", lambda tabla: repo)

    listar_eventos()

    assert repo.filtros == {"activo": True}


def test_area_id_resuelve_nombre_id_y_todas():
    areas = [
        {"id_area": 1, "nombre_area": "Barra"},
        {"id_area": 2, "nombre_area": "Cocina"},
    ]
    assert area_id("Barra", areas) == 1
    assert area_id("cocina", areas) == 2
    assert area_id("1", areas) == 1
    assert area_id("Todas", areas) is None
    assert area_id("Bodega", areas) is None
