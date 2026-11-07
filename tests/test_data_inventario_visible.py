"""Pruebas del read model de inventario y dashboard de la Etapa 3."""
from copy import deepcopy

import pytest

from core.exceptions import AuthorizationError
from data.inventario import (
    filtrar_inventario,
    inventario_visible,
    resumen_inventario,
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


def _producto(
    id_producto,
    nombre="Producto",
    categoria="General",
    unidad="unidad",
    minimo=10,
    maximo=20,
    costo=1000,
):
    return {
        "id_producto": id_producto,
        "nombre_producto": nombre,
        "categoria": categoria,
        "unidad_medida": unidad,
        "stock_minimo": minimo,
        "stock_maximo": maximo,
        "costo_base": costo,
        "activo": True,
    }


def _montar(monkeypatch, productos, snapshot):
    llamadas = {"snapshot": [], "productos": 0}

    def fake_snapshot(*, usuario=None):
        llamadas["snapshot"].append(usuario)
        resumen = {}
        for llave, valor in snapshot.items():
            if isinstance(valor, dict):
                resumen[llave] = dict(valor)
            else:
                resumen[llave] = {
                    "stock": valor,
                    "entradas": 0,
                    "salidas": 0,
                    "mermas": 0,
                    "ajustes_positivos": 0,
                    "ajustes_negativos": 0,
                }
        return resumen

    def fake_productos(solo_activos=True):
        llamadas["productos"] += 1
        return productos

    monkeypatch.setattr(
        "data.inventario.resumen_movimientos_por_producto_area",
        fake_snapshot,
    )
    monkeypatch.setattr("data.inventario.listar_productos", fake_productos)
    return llamadas


def test_admin_suma_stock_de_todas_las_areas(monkeypatch):
    _montar(
        monkeypatch,
        [_producto(1, minimo=10)],
        {(1, 1): 4, (1, 2): 6},
    )

    filas = inventario_visible(usuario=ADMIN)

    assert len(filas) == 1
    assert filas[0]["stock_actual"] == 10
    assert filas[0]["estado"] == "Disponible"


def test_admin_ve_productos_sin_movimientos_como_sin_stock(monkeypatch):
    _montar(
        monkeypatch,
        [_producto(1), _producto(2, nombre="Sin movimientos", minimo=5)],
        {(1, 1): 3},
    )

    filas = inventario_visible(usuario=ADMIN)

    assert [fila["id_producto"] for fila in filas] == [1, 2]
    sin_movimientos = next(fila for fila in filas if fila["id_producto"] == 2)
    assert sin_movimientos["stock_actual"] == 0
    assert sin_movimientos["estado"] == "Sin stock"


def test_operario_solo_ve_productos_con_stock_en_su_area(monkeypatch):
    llamadas = _montar(
        monkeypatch,
        [_producto(1), _producto(2, nombre="Solo otra área")],
        {(1, 1): 4},
    )

    filas = inventario_visible(usuario=OPERARIO)

    assert [fila["id_producto"] for fila in filas] == [1]
    assert filas[0]["stock_actual"] == 4
    assert llamadas["snapshot"][0] == OPERARIO
    assert llamadas["productos"] == 1


def test_operario_sin_movimientos_no_consulta_productos(monkeypatch):
    llamadas = _montar(monkeypatch, [_producto(1)], {})

    filas = inventario_visible(usuario=OPERARIO)

    assert filas == []
    assert llamadas["productos"] == 0


def test_inventario_expone_entradas_salidas_mermas_y_ajustes(monkeypatch):
    _montar(
        monkeypatch,
        [_producto(1, minimo=10)],
        {
            (1, 1): {
                "stock": 8,
                "entradas": 20,
                "salidas": 7,
                "mermas": 2,
                "ajustes_positivos": 4,
                "ajustes_negativos": 3,
            }
        },
    )

    filas = inventario_visible(usuario=ADMIN)
    fila = filas[0]

    assert fila["stock_actual"] == 8
    assert fila["entradas"] == 20
    assert fila["salidas"] == 7
    assert fila["mermas"] == 2
    assert fila["ajustes"] == 1
    assert fila["ajustes_positivos"] == 4
    assert fila["ajustes_negativos"] == 3


def test_stock_visible_suma_contadores_de_todas_las_areas(monkeypatch):
    _montar(
        monkeypatch,
        [_producto(1, minimo=100)],
        {
            (1, 1): {
                "stock": 5,
                "entradas": 10,
                "salidas": 5,
                "mermas": 0,
                "ajustes_positivos": 0,
                "ajustes_negativos": 0,
            },
            (1, 2): {
                "stock": 6,
                "entradas": 8,
                "salidas": 1,
                "mermas": 1,
                "ajustes_positivos": 0,
                "ajustes_negativos": 0,
            },
        },
    )

    fila = inventario_visible(usuario=ADMIN)[0]

    assert fila["stock_actual"] == 11
    assert fila["entradas"] == 18
    assert fila["salidas"] == 6
    assert fila["mermas"] == 1


def test_resumen_clasifica_los_cuatro_estados(monkeypatch):
    _montar(
        monkeypatch,
        [
            _producto(1, nombre="Uno", minimo=10),
            _producto(2, nombre="Dos", minimo=10),
            _producto(3, nombre="Tres", minimo=10),
            _producto(4, nombre="Cuatro", minimo=10),
        ],
        {(1, 1): 10, (2, 1): 8, (3, 1): 5, (4, 1): 0},
    )

    resumen = resumen_inventario(usuario=ADMIN)

    assert resumen["total_productos"] == 4
    assert resumen["disponibles"] == 1
    assert resumen["bajos"] == 1
    assert resumen["criticos"] == 1
    assert resumen["sin_stock"] == 1


def test_valor_estimado_solo_usa_costo_y_stock_validos(monkeypatch):
    _montar(
        monkeypatch,
        [
            _producto(1, nombre="Valorizable", minimo=1, costo=1000),
            _producto(2, nombre="Sin costo", minimo=1, costo=None),
            _producto(3, nombre="Sin stock", minimo=1, costo=500),
            _producto(4, nombre="Stock negativo", minimo=1, costo=100),
        ],
        {(1, 1): 2, (2, 1): 5, (3, 1): 0, (4, 1): -2},
    )

    resumen = resumen_inventario(usuario=ADMIN)

    assert resumen["valor_estimado"] == 2000
    assert resumen["productos_valorizados"] == 1
    assert resumen["productos_con_costo"] == 3


def test_valor_estimado_es_none_sin_productos(monkeypatch):
    _montar(monkeypatch, [], {})

    resumen = resumen_inventario(usuario=ADMIN)

    assert resumen["total_productos"] == 0
    assert resumen["valor_estimado"] is None
    assert resumen["productos_con_costo"] == 0


def test_valor_estimado_excluye_costo_cero(monkeypatch):
    _montar(
        monkeypatch,
        [_producto(1, minimo=1, costo=0)],
        {(1, 1): 10},
    )

    filas = inventario_visible(usuario=ADMIN)
    resumen = resumen_inventario(usuario=ADMIN)

    assert filas[0]["costo_base"] is None
    assert resumen["valor_estimado"] is None


def test_inventario_requiere_sesion():
    with pytest.raises(AuthorizationError):
        inventario_visible(usuario={})


FILAS_FILTRO = [
    {
        "id_producto": 1,
        "nombre": "Tomate",
        "categoria": "Verduras",
        "estado": "Disponible",
    },
    {
        "id_producto": 2,
        "nombre": "Harina",
        "categoria": "Insumos",
        "estado": "Crítico",
    },
    {
        "id_producto": 3,
        "nombre": "Aceite",
        "categoria": "Insumos",
        "estado": "Bajo",
    },
]


def test_busqueda_por_nombre_o_categoria():
    assert [f["id_producto"] for f in filtrar_inventario(FILAS_FILTRO, texto="tom")] == [1]
    assert [f["id_producto"] for f in filtrar_inventario(FILAS_FILTRO, texto="insum")] == [2, 3]


def test_filtro_por_categoria_y_estado():
    assert [
        f["id_producto"]
        for f in filtrar_inventario(FILAS_FILTRO, categoria="Insumos")
    ] == [2, 3]
    assert [
        f["id_producto"]
        for f in filtrar_inventario(FILAS_FILTRO, estado="Crítico")
    ] == [2]


def test_filtros_combinados_y_valores_neutros():
    assert [
        f["id_producto"]
        for f in filtrar_inventario(
            FILAS_FILTRO,
            texto="aceite",
            categoria="Insumos",
            estado="Bajo",
        )
    ] == [3]
    assert filtrar_inventario(
        FILAS_FILTRO, categoria="Todas", estado="Todos"
    ) == FILAS_FILTRO


def test_filtros_no_modifican_las_filas_originales():
    original = deepcopy(FILAS_FILTRO)

    filtrar_inventario(FILAS_FILTRO, texto="harina", estado="Crítico")

    assert FILAS_FILTRO == original
