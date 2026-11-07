"""Pruebas de las lecturas de productos."""
import pytest

from core.exceptions import SupabaseConnectionError
from data.errors import CONEXION, ErrorDatos
from data.productos import buscar_productos, listar_productos


class FakeProductosService:
    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.solo_activos = None

    def listar_productos(self, solo_activos=True):
        self.solo_activos = solo_activos
        if self.error:
            raise self.error
        return self.filas


class FakeProductosRepo:
    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.termino = None

    def buscar_estricto(self, termino):
        self.termino = termino
        if self.error:
            raise self.error
        return self.filas


def test_listar_productos_reutiliza_servicio(monkeypatch):
    servicio = FakeProductosService([{"id_producto": 1, "activo": True}])
    monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)

    productos = listar_productos(solo_activos=False)

    assert productos == [{"id_producto": 1, "activo": True}]
    assert servicio.solo_activos is False


def test_busqueda_corta_no_consulta(monkeypatch):
    repo = FakeProductosRepo([{"id_producto": 1}])
    monkeypatch.setattr("data.productos.ProductosRepository", lambda: repo)

    assert buscar_productos("a") == []
    assert repo.termino is None


def test_busqueda_filtra_inactivos(monkeypatch):
    repo = FakeProductosRepo(
        [
            {"id_producto": 1, "activo": True},
            {"id_producto": 2, "activo": False},
        ]
    )
    monkeypatch.setattr("data.productos.ProductosRepository", lambda: repo)

    assert [fila["id_producto"] for fila in buscar_productos("tomate")] == [1]


def test_error_de_conexion_se_traduce(monkeypatch):
    servicio = FakeProductosService(error=SupabaseConnectionError("sin red"))
    monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)

    with pytest.raises(ErrorDatos) as info:
        listar_productos()

    assert info.value.tipo == CONEXION
