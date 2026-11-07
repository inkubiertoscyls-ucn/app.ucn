"""Pruebas de las lecturas estrictas agregadas a los repositorios."""
from types import SimpleNamespace

import httpx
import pytest

from repositories.movimientos import MovimientosRepository


class FakeQuery:
    def __init__(self, filas, error=None):
        self.filas = filas
        self.error = error
        self.rangos = []
        self._inicio = 0
        self._fin = 0

    def select(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def range(self, inicio, fin):
        self.rangos.append((inicio, fin))
        self._inicio = inicio
        self._fin = fin
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.filas[self._inicio:self._fin + 1])


class FakeClient:
    def __init__(self, query):
        self.query = query

    def table(self, nombre):
        return self.query


def _repo_con(query):
    repo = object.__new__(MovimientosRepository)
    repo.table_name = "hecho_inventario"
    repo.client = FakeClient(query)
    return repo


def test_stock_agregado_recorre_todas_las_paginas():
    filas = [
        {"id_producto": i, "id_area": 1, "cantidad": 1}
        for i in range(1, 6)
    ]
    query = FakeQuery(filas)
    repo = _repo_con(query)

    resultado = repo.stock_agregado(tamano_pagina=2)

    assert len(resultado) == 5
    assert query.rangos == [(0, 1), (2, 3), (4, 5)]


def test_stock_agregado_propaga_error_de_conexion():
    repo = _repo_con(FakeQuery([], error=httpx.ConnectError("sin red")))

    with pytest.raises(httpx.ConnectError):
        repo.stock_agregado()
