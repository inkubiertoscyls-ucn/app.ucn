"""Pruebas de las alertas de stock y de la definición D4-A."""
from datetime import date

from data.alertas import _recuperados, resumen_alertas

FILAS = [
    {
        "id_producto": 1,
        "nombre": "Tomate",
        "categoria": "Verduras",
        "unidad": "kg",
        "stock_actual": 12,
        "stock_minimo": 10,
        "estado": "Disponible",
    },
    {
        "id_producto": 2,
        "nombre": "Harina",
        "categoria": "Insumos",
        "unidad": "kg",
        "stock_actual": 4,
        "stock_minimo": 10,
        "estado": "Crítico",
    },
    {
        "id_producto": 3,
        "nombre": "Aceite",
        "categoria": "Insumos",
        "unidad": "L",
        "stock_actual": 8,
        "stock_minimo": 10,
        "estado": "Bajo",
    },
    {
        "id_producto": 4,
        "nombre": "Sal",
        "categoria": "Insumos",
        "unidad": "kg",
        "stock_actual": 0,
        "stock_minimo": 5,
        "estado": "Sin stock",
    },
]

TIPOS = {
    1: {"id_tipo_movimiento": 1, "tipo_movimiento": "Entrada", "factor_stock": 1},
    2: {"id_tipo_movimiento": 2, "tipo_movimiento": "Salida", "factor_stock": -1},
    4: {"id_tipo_movimiento": 4, "tipo_movimiento": "Ajuste positivo", "factor_stock": 1},
}
AREAS = {1: "Barra", 2: "Cocina"}


def _movimiento(
    id_producto,
    cantidad,
    id_tipo,
    id_area=1,
    fecha="2026-11-03T10:00:00",
    id_hecho=1,
):
    return {
        "id_hecho_inventario": id_hecho,
        "id_producto": id_producto,
        "id_area": id_area,
        "id_tipo_movimiento": id_tipo,
        "cantidad": cantidad,
        "rut_usuario": "11111111-1",
        "fecha_hora_registro": fecha,
    }


def test_recuperado_cuando_entrada_cruza_el_minimo():
    movimientos = [_movimiento(1, 5, 1)]

    recuperados = _recuperados(FILAS, movimientos, TIPOS, AREAS)

    assert len(recuperados) == 1
    assert recuperados[0]["producto"] == "Tomate"
    assert recuperados[0]["stock_despues"] == 12
    assert recuperados[0]["area"] == "Barra"


def test_no_se_recupera_si_ya_estaba_sobre_el_minimo():
    filas = [{**FILAS[0], "stock_actual": 20}]
    movimientos = [_movimiento(1, 5, 1)]

    assert _recuperados(filas, movimientos, TIPOS, AREAS) == []


def test_ajuste_positivo_no_cuenta_como_entrada():
    filas = [{**FILAS[0], "stock_actual": 12}]
    movimientos = [_movimiento(1, 5, 4)]

    assert _recuperados(filas, movimientos, TIPOS, AREAS) == []


def test_secuencia_salida_y_entrada_del_dia():
    filas = [{**FILAS[0], "stock_actual": 13}]
    movimientos = [
        _movimiento(1, 2, 2, fecha="2026-11-03T09:00:00", id_hecho=1),
        _movimiento(1, 10, 1, fecha="2026-11-03T10:00:00", id_hecho=2),
    ]

    recuperados = _recuperados(filas, movimientos, TIPOS, AREAS)

    assert len(recuperados) == 1
    assert recuperados[0]["stock_despues"] == 13
    assert recuperados[0]["recuperado_a"] == "2026-11-03T10:00:00"


def test_producto_fuera_del_inventario_visible_se_ignora():
    movimientos = [_movimiento(99, 5, 1)]

    assert _recuperados(FILAS, movimientos, TIPOS, AREAS) == []


def test_resumen_agrupa_estados_y_recuperados(monkeypatch):
    monkeypatch.setattr(
        "data.alertas.inventario_visible",
        lambda *, usuario=None: FILAS,
    )
    movimientos = [_movimiento(1, 5, 1)]
    monkeypatch.setattr(
        "data.alertas.historial",
        lambda **kwargs: movimientos,
    )
    monkeypatch.setattr(
        "data.alertas.listar_tipos_movimiento",
        lambda incluir_inactivos=False: list(TIPOS.values()),
    )
    monkeypatch.setattr(
        "data.alertas.listar_areas",
        lambda incluir_inactivas=False: [
            {"id_area": 1, "nombre_area": "Barra"},
            {"id_area": 2, "nombre_area": "Cocina"},
        ],
    )

    resumen = resumen_alertas(usuario={"rol": "Administrador"}, hoy=date(2026, 11, 3))

    assert resumen["conteos"] == {
        "sin_stock": 1,
        "criticos": 1,
        "bajos": 1,
        "recuperados": 1,
    }
    assert len(resumen["sin_stock"]) == 1
    assert len(resumen["criticos"]) == 1
    assert len(resumen["bajos"]) == 1
    assert resumen["fecha"] == date(2026, 11, 3)


def test_resumen_sin_productos(monkeypatch):
    monkeypatch.setattr(
        "data.alertas.inventario_visible",
        lambda *, usuario=None: [],
    )
    monkeypatch.setattr("data.alertas.historial", lambda **kwargs: [])
    monkeypatch.setattr(
        "data.alertas.listar_tipos_movimiento",
        lambda incluir_inactivos=False: [],
    )
    monkeypatch.setattr(
        "data.alertas.listar_areas",
        lambda incluir_inactivas=False: [],
    )

    resumen = resumen_alertas(usuario={"rol": "Administrador"})

    assert resumen["conteos"] == {
        "sin_stock": 0,
        "criticos": 0,
        "bajos": 0,
        "recuperados": 0,
    }
    assert resumen["total_productos"] == 0
