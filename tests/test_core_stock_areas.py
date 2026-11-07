"""Pruebas de las reglas puras compartidas de stock y áreas."""
from core.areas import resolver_area_id
from core.stock import (
    calcular_stock,
    calcular_stock_agregado,
    clasificar_stock,
    normalizar_tipo_movimiento,
    resumir_movimientos,
)

AREAS = [
    {"id_area": 1, "nombre_area": "Barra"},
    {"id_area": 2, "nombre_area": "Cocina"},
]


def test_calcular_stock_con_factores():
    movimientos = [
        {"cantidad": 10, "dim_tipo_movimiento": {"factor_stock": 1}},
        {"cantidad": 3, "dim_tipo_movimiento": {"factor_stock": -1}},
    ]
    assert calcular_stock(movimientos) == 7


def test_calcular_stock_tolera_datos_incompletos():
    movimientos = [
        {"cantidad": 5},
        {"cantidad": 2, "dim_tipo_movimiento": None},
        {"cantidad": None, "dim_tipo_movimiento": {"factor_stock": 1}},
    ]
    assert calcular_stock(movimientos) == 0


def test_calcular_stock_agregado_por_producto_area():
    movimientos = [
        {"id_producto": 1, "id_area": 1, "cantidad": 4, "dim_tipo_movimiento": {"factor_stock": 1}},
        {"id_producto": 1, "id_area": 1, "cantidad": 1, "dim_tipo_movimiento": {"factor_stock": -1}},
        {"id_producto": 1, "id_area": 2, "cantidad": 9, "dim_tipo_movimiento": {"factor_stock": 1}},
        {"id_producto": None, "id_area": 1, "cantidad": 9, "dim_tipo_movimiento": {"factor_stock": 1}},
    ]
    assert calcular_stock_agregado(movimientos) == {(1, 1): 3, (1, 2): 9}


def _movimiento(id_producto, id_area, cantidad, tipo, factor):
    return {
        "id_producto": id_producto,
        "id_area": id_area,
        "cantidad": cantidad,
        "dim_tipo_movimiento": {
            "tipo_movimiento": tipo,
            "factor_stock": factor,
        },
    }


def test_resumir_movimientos_separa_cada_tipo_y_conserva_el_stock():
    movimientos = [
        _movimiento(1, 1, 10, "Entrada", 1),
        _movimiento(1, 1, 3, "Salida", -1),
        _movimiento(1, 1, 2, "Merma", -1),
        _movimiento(1, 1, 4, "Ajuste positivo", 1),
        _movimiento(1, 1, 1, "Ajuste negativo", -1),
        _movimiento(1, 2, 6, "Entrada", 1),
    ]

    resumen = resumir_movimientos(movimientos)

    assert resumen[(1, 1)] == {
        "stock": 8,
        "entradas": 10,
        "salidas": 3,
        "mermas": 2,
        "ajustes_positivos": 4,
        "ajustes_negativos": 1,
    }
    assert resumen[(1, 2)]["stock"] == 6
    assert calcular_stock_agregado(movimientos) == {
        llave: datos["stock"] for llave, datos in resumen.items()
    }


def test_resumir_movimientos_normaliza_tildes_y_mayusculas():
    movimientos = [
        _movimiento(1, 1, 5, "  ENTRADA ", 1),
        _movimiento(1, 1, 1, "Ajuste  Positivo", 1),
        _movimiento(1, 1, 2, "Tipo desconocido", -1),
    ]

    resumen = resumir_movimientos(movimientos)[(1, 1)]

    assert resumen["entradas"] == 5
    assert resumen["ajustes_positivos"] == 1
    assert resumen["stock"] == 4
    assert normalizar_tipo_movimiento("Ajuste Positivo") == "ajuste positivo"


def test_resumir_movimientos_ignora_filas_sin_producto_o_area():
    movimientos = [
        {"id_producto": None, "id_area": 1, "cantidad": 3},
        {"id_producto": 1, "id_area": None, "cantidad": 3},
    ]

    assert resumir_movimientos(movimientos) == {}


def test_resolver_area_id():
    assert resolver_area_id("Barra", AREAS) == 1
    assert resolver_area_id("cocina", AREAS) == 2
    assert resolver_area_id("2", AREAS) == 2
    assert resolver_area_id("Todas", AREAS) is None
    assert resolver_area_id("Bodega", AREAS) is None


def test_clasificar_stock_mantiene_reglas_ui():
    assert clasificar_stock(0, 10) == "Sin stock"
    assert clasificar_stock(6, 10) == "Crítico"
    assert clasificar_stock(8, 10) == "Bajo"
    assert clasificar_stock(10, 10) == "Disponible"
