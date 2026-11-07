"""Pruebas del registro y el historial de movimientos (Etapa 4)."""
from copy import deepcopy

import pytest

from core.exceptions import AuthorizationError
from data.errors import VALIDACION, ErrorDatos
from data.movimientos import (
    CLAVE_ULTIMO_MOVIMIENTO,
    historial_movimientos,
    registrar_movimiento,
)

ADMIN = {
    "rut_usuario": "12345678-9",
    "nombre_usuario": "Admin",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
}
OPERARIO = {
    "rut_usuario": "11111111-1",
    "nombre_usuario": "Operario Barra",
    "rol": "Operario",
    "area_asignada": "Barra",
    "activo": True,
}

AREAS = [
    {"id_area": 1, "nombre_area": "Barra", "activo": True},
    {"id_area": 2, "nombre_area": "Cocina", "activo": True},
]
TIPOS = [
    {"id_tipo_movimiento": 1, "tipo_movimiento": "Entrada", "factor_stock": 1},
    {"id_tipo_movimiento": 2, "tipo_movimiento": "Salida", "factor_stock": -1},
    {"id_tipo_movimiento": 3, "tipo_movimiento": "Merma", "factor_stock": -1},
    {"id_tipo_movimiento": 4, "tipo_movimiento": "Ajuste positivo", "factor_stock": 1},
    {"id_tipo_movimiento": 5, "tipo_movimiento": "Ajuste negativo", "factor_stock": -1},
]
PRODUCTOS = [
    {
        "id_producto": 1,
        "nombre_producto": "Tomate",
        "categoria": "Verduras",
        "unidad_medida": "kg",
        "stock_minimo": 10,
        "stock_maximo": 30,
        "costo_base": 500,
        "activo": True,
    },
    {
        "id_producto": 2,
        "nombre_producto": "Harina",
        "categoria": "Insumos",
        "unidad_medida": "kg",
        "stock_minimo": 5,
        "stock_maximo": 20,
        "costo_base": 800,
        "activo": True,
    },
]


class FakeServicio:
    def __init__(self):
        self.llamadas = []

    def _registrar(self, nombre, data):
        self.llamadas.append((nombre, dict(data)))
        return {"id_hecho_inventario": len(self.llamadas), **data}

    def registrar_entrada(self, data):
        return self._registrar("entrada", data)

    def registrar_salida(self, data):
        return self._registrar("salida", data)

    def registrar_merma(self, data):
        return self._registrar("merma", data)

    def registrar_ajuste_positivo(self, data):
        return self._registrar("ajuste_positivo", data)

    def registrar_ajuste_negativo(self, data):
        return self._registrar("ajuste_negativo", data)


class FakeStock:
    def __init__(self, valor):
        self.valor = valor
        self.llamadas = []

    def __call__(self, id_producto, id_area=None, *, usuario=None):
        self.llamadas.append((id_producto, id_area, usuario))
        return self.valor


@pytest.fixture(autouse=True)
def _limpiar_duplicados():
    import streamlit as st

    st.session_state.pop(CLAVE_ULTIMO_MOVIMIENTO, None)
    yield
    st.session_state.pop(CLAVE_ULTIMO_MOVIMIENTO, None)


def _montar(monkeypatch, stock=10):
    servicio = FakeServicio()
    consulta_stock = FakeStock(stock)
    limpiezas = []
    monkeypatch.setattr(
        "data.movimientos.listar_productos",
        lambda solo_activos=True: deepcopy(PRODUCTOS),
    )
    monkeypatch.setattr(
        "data.movimientos.listar_tipos_movimiento",
        lambda incluir_inactivos=False: deepcopy(TIPOS),
    )
    monkeypatch.setattr(
        "data.movimientos.listar_areas",
        lambda incluir_inactivas=False: deepcopy(AREAS),
    )
    monkeypatch.setattr("data.movimientos.stock_actual", consulta_stock)
    monkeypatch.setattr("data.movimientos.InventarioService", lambda: servicio)
    monkeypatch.setattr(
        "data.movimientos.limpiar_cache",
        lambda: limpiezas.append(True),
    )
    return servicio, consulta_stock, limpiezas


def test_entrada_registra_con_servicio_y_actualiza_stock(monkeypatch):
    servicio, _, limpiezas = _montar(monkeypatch, stock=10)

    resultado = registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=1,
        cantidad=5,
        id_area=1,
        costo_unitario=1250,
        observacion="Compra semanal",
        usuario=ADMIN,
    )

    assert servicio.llamadas[0][0] == "entrada"
    datos = servicio.llamadas[0][1]
    assert datos["id_area"] == 1
    assert datos["cantidad"] == 5
    assert datos["costo_unitario"] == 1250
    assert datos["observacion"] == "Compra semanal"
    assert resultado["costo_unitario"] == 1250
    assert resultado["stock_anterior"] == 10
    assert resultado["stock_nuevo"] == 15
    assert limpiezas == [True]


def test_costo_unitario_usa_costo_base_si_no_se_informa(monkeypatch):
    servicio, _, _ = _montar(monkeypatch, stock=10)

    resultado = registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=1,
        cantidad=5,
        id_area=1,
        usuario=ADMIN,
    )

    datos = servicio.llamadas[0][1]
    assert datos["costo_unitario"] == 500
    assert resultado["costo_unitario"] == 500


@pytest.mark.parametrize("costo", [-1, "abc", float("inf")])
def test_costo_unitario_invalido_no_escribe(monkeypatch, costo):
    servicio, _, _ = _montar(monkeypatch, stock=10)

    with pytest.raises(ErrorDatos) as info:
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=1,
            cantidad=1,
            id_area=1,
            costo_unitario=costo,
            usuario=ADMIN,
        )

    assert info.value.tipo == VALIDACION
    assert servicio.llamadas == []


def test_cantidad_cero_o_negativa_no_escribe(monkeypatch):
    servicio, _, _ = _montar(monkeypatch)

    for cantidad in (0, -3):
        with pytest.raises(ErrorDatos) as info:
            registrar_movimiento(
                id_producto=1,
                id_tipo_movimiento=1,
                cantidad=cantidad,
                id_area=1,
                usuario=ADMIN,
            )
        assert info.value.tipo == VALIDACION

    assert servicio.llamadas == []


def test_cantidad_decimal_no_escribe(monkeypatch):
    servicio, _, _ = _montar(monkeypatch)

    with pytest.raises(ErrorDatos):
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=1,
            cantidad=1.5,
            id_area=1,
            usuario=ADMIN,
        )

    assert servicio.llamadas == []


def test_salida_valida_stock_antes_de_escribir(monkeypatch):
    servicio, _, _ = _montar(monkeypatch, stock=3)

    with pytest.raises(ErrorDatos) as info:
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=2,
            cantidad=4,
            id_area=1,
            usuario=ADMIN,
        )

    assert info.value.tipo == VALIDACION
    assert "Stock insuficiente" in info.value.mensaje
    assert "disponible 3 kg" in info.value.mensaje
    assert servicio.llamadas == []


def test_salida_con_stock_suficiente_registra(monkeypatch):
    servicio, _, _ = _montar(monkeypatch, stock=10)

    resultado = registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=2,
        cantidad=4,
        id_area=1,
        usuario=ADMIN,
    )

    assert servicio.llamadas[0][0] == "salida"
    assert resultado["factor"] == -1
    assert resultado["stock_nuevo"] == 6


@pytest.mark.parametrize(
    "usuario,id_tipo,metodo",
    [
        (ADMIN, 1, "entrada"),
        (ADMIN, 2, "salida"),
        (OPERARIO, 1, "entrada"),
        (OPERARIO, 2, "salida"),
    ],
)
def test_entradas_y_salidas_para_admin_y_operario(
    monkeypatch, usuario, id_tipo, metodo
):
    servicio, _, _ = _montar(monkeypatch, stock=10)

    resultado = registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=id_tipo,
        cantidad=2,
        id_area=1 if usuario is ADMIN else None,
        usuario=usuario,
    )

    assert servicio.llamadas[0][0] == metodo
    assert servicio.llamadas[0][1]["id_area"] == 1
    assert servicio.llamadas[0][1]["costo_unitario"] == 500
    assert resultado["stock_nuevo"] == (12 if metodo == "entrada" else 8)


def test_operario_usa_siempre_su_area(monkeypatch):
    servicio, consulta_stock, _ = _montar(monkeypatch, stock=10)

    registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=3,
        cantidad=2,
        usuario=OPERARIO,
    )

    assert servicio.llamadas[0][1]["id_area"] == 1
    assert consulta_stock.llamadas[0][:2] == (1, 1)


def test_operario_no_puede_registrar_en_otra_area(monkeypatch):
    servicio, _, _ = _montar(monkeypatch)

    with pytest.raises(AuthorizationError):
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=1,
            cantidad=1,
            id_area=2,
            usuario=OPERARIO,
        )

    assert servicio.llamadas == []


def test_admin_debe_elegir_area(monkeypatch):
    servicio, _, _ = _montar(monkeypatch)

    with pytest.raises(ErrorDatos) as info:
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=1,
            cantidad=1,
            usuario=ADMIN,
        )

    assert info.value.tipo == VALIDACION
    assert servicio.llamadas == []


@pytest.mark.parametrize(
    "id_tipo,metodo,stock",
    [
        (1, "entrada", 5),
        (2, "salida", 1),
        (3, "merma", 1),
        (4, "ajuste_positivo", 5),
        (5, "ajuste_negativo", 5),
    ],
)
def test_cada_tipo_usa_su_metodo(monkeypatch, id_tipo, metodo, stock):
    servicio, _, _ = _montar(monkeypatch, stock=stock)

    registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=id_tipo,
        cantidad=1,
        id_area=1,
        usuario=ADMIN,
    )

    assert servicio.llamadas[0][0] == metodo


def test_tipo_inexistente_no_escribe(monkeypatch):
    servicio, _, _ = _montar(monkeypatch)

    with pytest.raises(ErrorDatos):
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=99,
            cantidad=1,
            id_area=1,
            usuario=ADMIN,
        )

    assert servicio.llamadas == []


def test_duplicado_inmediato_se_bloquea(monkeypatch):
    servicio, _, _ = _montar(monkeypatch, stock=10)

    registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=1,
        cantidad=2,
        id_area=1,
        usuario=ADMIN,
    )
    with pytest.raises(ErrorDatos) as info:
        registrar_movimiento(
            id_producto=1,
            id_tipo_movimiento=1,
            cantidad=2,
            id_area=1,
            usuario=ADMIN,
        )

    assert "ya fue registrado" in info.value.mensaje
    assert len(servicio.llamadas) == 1


def test_movimiento_distinto_no_se_bloquea(monkeypatch):
    servicio, _, _ = _montar(monkeypatch, stock=10)

    registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=1,
        cantidad=2,
        id_area=1,
        usuario=ADMIN,
    )
    registrar_movimiento(
        id_producto=1,
        id_tipo_movimiento=1,
        cantidad=3,
        id_area=1,
        usuario=ADMIN,
    )

    assert len(servicio.llamadas) == 2


def test_historial_enriquece_cantidad_y_responsable(monkeypatch):
    filas = [
        {
            "id_hecho_inventario": 10,
            "id_producto": 1,
            "id_area": 1,
            "id_tipo_movimiento": 2,
            "rut_usuario": "11111111-1",
            "cantidad": 3,
            "costo_unitario": 1200,
            "observacion": "[INK-IMPORT:" + "a" * 64 + ":7] Compra de barra",
            "fecha_hora_registro": "2026-11-03T10:00:00",
        },
        {
            "id_hecho_inventario": 9,
            "id_producto": 2,
            "id_area": 2,
            "id_tipo_movimiento": 1,
            "rut_usuario": "22222222-2",
            "cantidad": 7,
            "observacion": "",
            "fecha_hora_registro": "2026-11-03T09:00:00",
        },
    ]
    llamadas = []

    def fake_historial(**kwargs):
        llamadas.append(kwargs)
        return filas

    monkeypatch.setattr("data.movimientos.historial", fake_historial)
    monkeypatch.setattr(
        "data.movimientos._mapas_historial",
        lambda: (
            {1: PRODUCTOS[0], 2: PRODUCTOS[1]},
            {1: "Barra", 2: "Cocina"},
            {1: TIPOS[0], 2: TIPOS[1]},
            {"11111111-1": "Operario Barra"},
        ),
    )

    resultado = historial_movimientos(usuario=ADMIN)

    assert resultado[0]["producto"] == "Tomate"
    assert resultado[0]["usuario"] == "Operario Barra"
    assert resultado[0]["cantidad"] == 3
    assert resultado[0]["cantidad_firmada"] == -3
    assert resultado[0]["factor"] == -1
    assert resultado[0]["costo_unitario"] == 1200
    assert resultado[0]["costo_total"] == 3600
    assert resultado[0]["observacion"] == "Compra de barra"
    assert llamadas[0]["usuario"] == ADMIN


def test_historial_filtra_por_texto_y_pasa_filtros(monkeypatch):
    filas = [
        {
            "id_hecho_inventario": 1,
            "id_producto": 1,
            "id_area": 1,
            "id_tipo_movimiento": 1,
            "rut_usuario": "11111111-1",
            "cantidad": 5,
            "observacion": "Compra de verduras",
            "fecha_hora_registro": "2026-11-03T10:00:00",
        },
        {
            "id_hecho_inventario": 2,
            "id_producto": 2,
            "id_area": 1,
            "id_tipo_movimiento": 1,
            "rut_usuario": "11111111-1",
            "cantidad": 4,
            "observacion": "Compra de insumos",
            "fecha_hora_registro": "2026-11-03T11:00:00",
        },
    ]
    llamadas = []
    monkeypatch.setattr(
        "data.movimientos.historial",
        lambda **kwargs: llamadas.append(kwargs) or filas,
    )
    monkeypatch.setattr(
        "data.movimientos._mapas_historial",
        lambda: (
            {1: PRODUCTOS[0], 2: PRODUCTOS[1]},
            {1: "Barra"},
            {1: TIPOS[0]},
            {},
        ),
    )

    resultado = historial_movimientos(
        usuario=ADMIN,
        texto="verduras",
        id_producto=1,
        id_tipo_movimiento=1,
        id_area=1,
        desde="2026-11-01",
        hasta="2026-11-03",
    )

    assert [fila["id"] for fila in resultado] == [1]
    assert llamadas[0]["id_producto"] == 1
    assert llamadas[0]["id_tipo_movimiento"] == 1
    assert llamadas[0]["id_area"] == 1
    assert llamadas[0]["desde"] == "2026-11-01"


def test_historial_requiere_sesion():
    with pytest.raises(AuthorizationError):
        historial_movimientos(usuario={})
