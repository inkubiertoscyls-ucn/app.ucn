"""Pruebas de las reglas de presentación acordadas para el frontend."""
from ui.format import estado_stock, fmt_cantidad, resolver_area


def test_estado_stock_sin_stock():
    assert estado_stock(0, 8) == "Sin stock"
    assert estado_stock(-1, 8) == "Sin stock"


def test_estado_stock_critico_bajo_y_disponible():
    assert estado_stock(5, 8) == "Crítico"
    assert estado_stock(11, 14) == "Bajo"
    assert estado_stock(15, 18) == "Bajo"
    assert estado_stock(10, 10) == "Disponible"
    assert estado_stock(20, 10) == "Disponible"


def test_estado_stock_sin_minimo_configurado():
    assert estado_stock(3, 0) == "Disponible"


def test_fmt_cantidad_enteros_y_miles():
    assert fmt_cantidad(10) == "10"
    assert fmt_cantidad(10.0) == "10"
    assert fmt_cantidad(1234) == "1.234"


def test_fmt_cantidad_decimales_sin_ceros_sobrantes():
    assert fmt_cantidad(10.5) == "10,5"
    assert fmt_cantidad(10.25) == "10,25"
    assert fmt_cantidad(0.5) == "0,5"


def test_fmt_cantidad_valores_no_numericos():
    assert fmt_cantidad(None) == "—"
    assert fmt_cantidad("abc") == "—"
    assert fmt_cantidad(float("nan")) == "—"
    assert fmt_cantidad(float("inf")) == "—"


def test_resolver_area_acepta_nombre_id_y_todas():
    areas = [
        {"id_area": 1, "nombre_area": "Barra"},
        {"id_area": 2, "nombre_area": "Cocina"},
    ]
    assert resolver_area("Todas", areas) == "Todas"
    assert resolver_area("1", areas) == "Barra"
    assert resolver_area("barra", areas) == "Barra"
    assert resolver_area("Bodega", areas) == "Bodega"
    assert resolver_area(None, areas) is None
