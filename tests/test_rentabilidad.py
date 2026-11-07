"""Pruebas de vinculación manual y cálculos de rentabilidad (Etapa 5)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.ventas import (
    calcular_resumen_rentabilidad,
    listar_ventas,
    resumen_rentabilidad,
    vincular_venta,
    vincular_ventas_por_nombre,
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

PRODUCTOS = [
    {
        "id_producto": 1,
        "nombre_producto": "Pisco Sour",
        "categoria": "Tragos",
        "costo_base": 1000,
    },
    {
        "id_producto": 2,
        "nombre_producto": "Empanada",
        "categoria": "Comida",
        "costo_base": None,
    },
]

EVENTOS = [{"id_evento": 7, "nombre_evento": "Noche de jazz"}]

VENTAS = [
    {
        "id_venta_fudo": 1,
        "fecha_venta": "2026-01-10",
        "id_evento": 7,
        "total_venta": 5000,
        "cantidad_total": 2,
        "producto_identificado": "Pisco Sour",
        "id_producto_relacionado": 1,
    },
    {
        "id_venta_fudo": 2,
        "fecha_venta": "2026-01-10",
        "id_evento": None,
        "total_venta": 4000,
        "cantidad_total": 2,
        "producto_identificado": "Empanada",
        "id_producto_relacionado": 2,
    },
    {
        "id_venta_fudo": 3,
        "fecha_venta": "2026-01-11",
        "id_evento": None,
        "total_venta": 1000,
        "cantidad_total": 1,
        "producto_identificado": "Producto pendiente",
        "id_producto_relacionado": None,
    },
    {
        "id_venta_fudo": 4,
        "fecha_venta": "2026-01-11",
        "id_evento": None,
        "total_venta": 2000,
        "cantidad_total": 1,
        "producto_identificado": "Producto eliminado",
        "id_producto_relacionado": 99,
    },
    {
        "id_venta_fudo": 5,
        "fecha_venta": "2026-01-12",
        "id_evento": None,
        "total_venta": 3000,
        "cantidad_total": None,
        "producto_identificado": "Pisco Sour",
        "id_producto_relacionado": 1,
    },
]


def test_resumen_separa_ventas_reales_de_estimaciones():
    resumen = calcular_resumen_rentabilidad(VENTAS, PRODUCTOS, EVENTOS)

    assert resumen["total_registros"] == 5
    assert resumen["ventas_totales"] == 15000
    assert resumen["cantidad_total"] == 6
    assert resumen["registros_sin_cantidad"] == 1

    assert resumen["ventas_identificadas"] == 4
    assert resumen["ventas_pendientes"] == 1
    assert resumen["monto_pendiente"] == 1000

    # Solo la venta 1 tiene producto, cantidad y costo válidos.
    assert resumen["ventas_con_costo"] == 1
    assert resumen["monto_con_costo"] == 5000
    assert resumen["costo_estimado"] == 2000
    assert resumen["utilidad_estimada"] == 3000
    assert resumen["margen_estimado"] == 60

    # Las otras tres identificadas no se suman como utilidad cero.
    assert resumen["ventas_identificadas_sin_costo"] == 3
    assert resumen["monto_identificado_sin_costo"] == 9000

    assert [fila["categoria"] for fila in resumen["por_categoria"]] == ["Tragos"]
    assert resumen["por_producto"][0]["id_producto"] == 1
    assert resumen["por_producto"][0]["margen"] == 60

    motivos = " ".join(fila["motivo"] for fila in resumen["sin_costo"])
    assert "costo" in motivos.lower()
    assert "cantidad" in motivos.lower()
    assert "existe" in motivos.lower()


def test_sin_costo_no_reporta_utilidad_cero():
    resumen = calcular_resumen_rentabilidad([VENTAS[1]], PRODUCTOS, EVENTOS)

    assert resumen["ventas_totales"] == 4000
    assert resumen["costo_estimado"] is None
    assert resumen["utilidad_estimada"] is None
    assert resumen["margen_estimado"] is None
    assert resumen["ventas_identificadas_sin_costo"] == 1


def test_ventas_sin_datos_no_inventan_cifras():
    resumen = calcular_resumen_rentabilidad([], PRODUCTOS, EVENTOS)

    assert resumen["con_datos"] is False
    assert resumen["ventas_totales"] == 0
    assert resumen["cantidad_total"] == 0
    assert resumen["costo_estimado"] is None
    assert resumen["utilidad_estimada"] is None
    assert resumen["margen_estimado"] is None
    assert resumen["por_categoria"] == []


def test_eventos_solo_agrupan_relaciones_ya_guardadas():
    resumen = calcular_resumen_rentabilidad(VENTAS, PRODUCTOS, EVENTOS)

    grupos = {fila["id_evento"]: fila for fila in resumen["eventos"]}
    assert grupos[7]["evento"] == "Noche de jazz"
    assert grupos[7]["registros"] == 1
    assert grupos[7]["ventas"] == 5000
    assert grupos[None]["registros"] == 4
    assert grupos[None]["evento"] == "Sin evento asignado"


def test_cantidad_cero_no_se_estima_como_utilidad_total():
    venta = {
        "id_venta_fudo": 10,
        "total_venta": 5000,
        "cantidad_total": 0,
        "producto_identificado": "Pisco Sour",
        "id_producto_relacionado": 1,
    }
    resumen = calcular_resumen_rentabilidad([venta], PRODUCTOS, EVENTOS)

    assert resumen["ventas_totales"] == 5000
    assert resumen["ventas_con_costo"] == 0
    assert resumen["costo_estimado"] is None
    assert resumen["utilidad_estimada"] is None
    assert resumen["ventas_identificadas_sin_costo"] == 1
    assert "Cantidad no válida" in resumen["sin_costo"][0]["motivo"]


def test_utilidad_puede_ser_negativa_sin_convertirla_en_cero():
    venta = {
        "id_venta_fudo": 9,
        "total_venta": 1000,
        "cantidad_total": 2,
        "producto_identificado": "Pisco Sour",
        "id_producto_relacionado": 1,
    }
    resumen = calcular_resumen_rentabilidad([venta], PRODUCTOS, EVENTOS)
    assert resumen["costo_estimado"] == 2000
    assert resumen["utilidad_estimada"] == -1000
    assert resumen["margen_estimado"] == -100


class FakeVentasRepo:
    def __init__(self):
        self.llamadas = []
        self.vinculadas = []

    def listar(self, **kwargs):
        self.llamadas.append(kwargs)
        return [{"id_venta_fudo": 1}]

    def actualizar_vinculacion(self, id_venta, id_producto):
        self.vinculadas.append((id_venta, id_producto))
        return [{"id_venta_fudo": id_venta}]

    def vincular_por_producto_identificado(self, nombre, id_producto):
        self.vinculadas.append((nombre, id_producto))
        return [1, 2]


class FakeProductosRepo:
    def __init__(self, producto=None):
        self.producto = producto

    def get_by_id(self, columna, valor):
        return self.producto


def test_listar_ventas_normaliza_filtros_y_exige_admin(monkeypatch):
    repo = FakeVentasRepo()
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: repo)

    listar_ventas(
        desde=date(2026, 1, 1),
        hasta=date(2026, 1, 31),
        solo_pendientes=True,
        texto="pisco",
        id_evento="7",
        limite=9999,
        usuario=ADMIN,
    )

    llamada = repo.llamadas[0]
    assert llamada["desde"] == "2026-01-01"
    assert llamada["hasta"] == "2026-01-31"
    assert llamada["solo_pendientes"] is True
    assert llamada["texto"] == "pisco"
    assert llamada["id_evento"] == 7
    assert llamada["limite"] == 500

    with pytest.raises(AuthorizationError):
        listar_ventas(usuario=OPERARIO)


def test_vincular_venta_solo_cambia_la_relacion(monkeypatch):
    repo = FakeVentasRepo()
    productos = FakeProductosRepo(
        {"id_producto": 1, "nombre_producto": "Pisco Sour"}
    )
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: repo)
    monkeypatch.setattr("data.ventas.ProductosRepository", lambda: productos)
    monkeypatch.setattr("data.ventas.limpiar_cache", lambda: None)

    resultado = vincular_venta(10, 1, usuario=ADMIN)

    assert resultado["actualizadas"] == 1
    assert resultado["producto"] == "Pisco Sour"
    assert repo.vinculadas == [(10, 1)]


def test_vincular_por_nombre_es_explicito_y_exige_admin(monkeypatch):
    repo = FakeVentasRepo()
    productos = FakeProductosRepo(
        {"id_producto": 1, "nombre_producto": "Pisco Sour"}
    )
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: repo)
    monkeypatch.setattr("data.ventas.ProductosRepository", lambda: productos)
    monkeypatch.setattr("data.ventas.limpiar_cache", lambda: None)

    resultado = vincular_ventas_por_nombre("Pisco Sour", 1, usuario=ADMIN)
    assert resultado["vinculadas"] == 2
    assert resultado["producto_identificado"] == "Pisco Sour"
    assert repo.vinculadas == [("Pisco Sour", 1)]

    with pytest.raises(AuthorizationError):
        vincular_ventas_por_nombre("Pisco Sour", 1, usuario=OPERARIO)

    with pytest.raises(ErrorDatos):
        vincular_ventas_por_nombre("   ", 1, usuario=ADMIN)


def test_vincular_producto_inexistente_no_escribe(monkeypatch):
    repo = FakeVentasRepo()
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: repo)
    monkeypatch.setattr(
        "data.ventas.ProductosRepository", lambda: FakeProductosRepo(None)
    )
    monkeypatch.setattr("data.ventas.limpiar_cache", lambda: None)

    with pytest.raises(ErrorDatos):
        vincular_venta(10, 1, usuario=ADMIN)
    assert repo.vinculadas == []


def test_resumen_rentabilidad_exige_admin(monkeypatch):
    monkeypatch.setattr("data.ventas._resumen", lambda *args: {"ok": True})

    assert resumen_rentabilidad(usuario=ADMIN) == {"ok": True}

    with pytest.raises(AuthorizationError):
        resumen_rentabilidad(usuario=OPERARIO)


def test_vinculacion_por_nombre_actualiza_en_lotes(monkeypatch):
    from repositories.ventas import VentasFudoRepository

    class FakeCliente:
        def __init__(self):
            self.lotes = []

        def table(self, _nombre):
            return self

        def update(self, _datos):
            return self

        def in_(self, _columna, valores):
            self.lotes.append(list(valores))
            return self

        def execute(self):
            return type("Respuesta", (), {"data": []})()

    cliente = FakeCliente()
    monkeypatch.setattr(
        "repositories.base.get_supabase_client", lambda: cliente
    )

    repo = VentasFudoRepository()
    repo.ids_por_producto_identificado = lambda _nombre: list(range(1, 251))

    ids = repo.vincular_por_producto_identificado("Pisco Sour", 5)

    assert len(ids) == 250
    assert [len(lote) for lote in cliente.lotes] == [100, 100, 50]
    assert cliente.lotes[0][0] == 1
    assert cliente.lotes[-1][-1] == 250
