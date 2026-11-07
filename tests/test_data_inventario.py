"""Pruebas de stock e historial de la capa de datos."""
import httpx
import pytest

from core.exceptions import AuthorizationError
from core.stock import calcular_stock_agregado
from data.errors import CONEXION, ErrorDatos
from data.inventario import (
    historial,
    resumen_movimientos_por_producto_area,
    stock_actual,
    stock_por_producto_area,
)

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


class FakeMovimientos:
    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.kwargs = None
        self.llamadas = 0

    def stock_agregado(self):
        self.llamadas += 1
        if self.error:
            raise self.error
        return self.filas

    def buscar_historial(self, **kwargs):
        self.llamadas += 1
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.filas


def _montar_repo(monkeypatch, repo):
    monkeypatch.setattr("data.inventario.MovimientosRepository", lambda: repo)
    return repo


def test_stock_una_sola_consulta_y_agrupado(monkeypatch):
    repo = _montar_repo(
        monkeypatch,
        FakeMovimientos(
            [
                {"id_producto": 1, "id_area": 1, "cantidad": 10, "dim_tipo_movimiento": {"factor_stock": 1}},
                {"id_producto": 1, "id_area": 1, "cantidad": 3, "dim_tipo_movimiento": {"factor_stock": -1}},
                {"id_producto": 1, "id_area": 2, "cantidad": 5, "dim_tipo_movimiento": {"factor_stock": 1}},
            ]
        ),
    )

    snapshot = stock_por_producto_area(usuario=ADMIN)

    assert snapshot[(1, 1)] == 7
    assert snapshot[(1, 2)] == 5
    assert repo.llamadas == 1


def test_snapshot_coincide_con_calculo_de_movimientos(monkeypatch):
    filas = [
        {"id_producto": 1, "id_area": 1, "cantidad": 10, "dim_tipo_movimiento": {"tipo_movimiento": "Entrada", "factor_stock": 1}},
        {"id_producto": 1, "id_area": 1, "cantidad": 3, "dim_tipo_movimiento": {"tipo_movimiento": "Salida", "factor_stock": -1}},
        {"id_producto": 1, "id_area": 1, "cantidad": 2, "dim_tipo_movimiento": {"tipo_movimiento": "Merma", "factor_stock": -1}},
        {"id_producto": 1, "id_area": 1, "cantidad": 4, "dim_tipo_movimiento": {"tipo_movimiento": "Ajuste positivo", "factor_stock": 1}},
        {"id_producto": 1, "id_area": 1, "cantidad": 1, "dim_tipo_movimiento": {"tipo_movimiento": "Ajuste negativo", "factor_stock": -1}},
        {"id_producto": 1, "id_area": 2, "cantidad": 6, "dim_tipo_movimiento": {"tipo_movimiento": "Entrada", "factor_stock": 1}},
    ]
    _montar_repo(monkeypatch, FakeMovimientos(filas))

    snapshot = stock_por_producto_area(usuario=ADMIN)
    resumen = resumen_movimientos_por_producto_area(usuario=ADMIN)

    assert snapshot == calcular_stock_agregado(filas)
    assert {
        llave: datos["stock"] for llave, datos in resumen.items()
    } == snapshot
    assert resumen[(1, 1)]["entradas"] == 10
    assert resumen[(1, 1)]["salidas"] == 3
    assert resumen[(1, 1)]["mermas"] == 2
    assert resumen[(1, 1)]["ajustes_positivos"] == 4
    assert resumen[(1, 1)]["ajustes_negativos"] == 1


def test_stock_actual_suma_todas_las_areas_para_admin(monkeypatch):
    _montar_repo(
        monkeypatch,
        FakeMovimientos(
            [
                {"id_producto": 1, "id_area": 1, "cantidad": 7, "dim_tipo_movimiento": {"factor_stock": 1}},
                {"id_producto": 1, "id_area": 2, "cantidad": 5, "dim_tipo_movimiento": {"factor_stock": 1}},
            ]
        ),
    )

    assert stock_actual(1, usuario=ADMIN) == 12
    assert stock_actual(1, id_area=2, usuario=ADMIN) == 5


def test_operario_no_puede_consultar_otra_area(monkeypatch):
    _montar_repo(
        monkeypatch,
        FakeMovimientos(
            [
                {"id_producto": 1, "id_area": 1, "cantidad": 7, "dim_tipo_movimiento": {"factor_stock": 1}},
                {"id_producto": 1, "id_area": 2, "cantidad": 99, "dim_tipo_movimiento": {"factor_stock": 1}},
            ]
        ),
    )
    monkeypatch.setattr("data.inventario.area_id", lambda nombre: 1)

    assert stock_actual(1, id_area=2, usuario=OPERARIO) == 7
    assert stock_por_producto_area(usuario=OPERARIO) == {(1, 1): 7}


def test_historial_fuerza_area_del_operario(monkeypatch):
    repo = _montar_repo(monkeypatch, FakeMovimientos([{"id_producto": 1}]))
    monkeypatch.setattr("data.inventario.area_id", lambda nombre: 1)

    filas = historial(id_area=2, usuario=OPERARIO)

    assert filas == [{"id_producto": 1}]
    assert repo.kwargs["id_area"] == 1


def test_historial_admin_conserva_filtro_de_area(monkeypatch):
    repo = _montar_repo(monkeypatch, FakeMovimientos([]))

    historial(id_area=2, usuario=ADMIN)

    assert repo.kwargs["id_area"] == 2


def test_historial_sin_fechas_en_rango_no_consulta(monkeypatch):
    repo = _montar_repo(monkeypatch, FakeMovimientos([]))
    monkeypatch.setattr("data.inventario.ids_fecha_entre", lambda desde, hasta: (None, None))

    filas = historial(desde="2020-01-01", hasta="2020-01-31", usuario=ADMIN)

    assert filas == []
    assert repo.kwargs is None


def test_historial_limita_resultados(monkeypatch):
    repo = _montar_repo(monkeypatch, FakeMovimientos([]))

    historial(limite=9999, usuario=ADMIN)

    assert repo.kwargs["limite"] == 500


def test_error_de_conexion_en_stock(monkeypatch):
    _montar_repo(monkeypatch, FakeMovimientos(error=httpx.ConnectError("sin red")))

    with pytest.raises(ErrorDatos) as info:
        stock_por_producto_area(usuario=ADMIN)

    assert info.value.tipo == CONEXION


def test_operario_sin_area_valida_no_consulta(monkeypatch):
    _montar_repo(monkeypatch, FakeMovimientos([]))
    monkeypatch.setattr("data.inventario.area_id", lambda nombre: None)

    with pytest.raises(ErrorDatos):
        stock_actual(1, usuario=OPERARIO)


def test_historial_requiere_sesion(monkeypatch):
    _montar_repo(monkeypatch, FakeMovimientos([]))

    with pytest.raises(AuthorizationError):
        historial(usuario={})
