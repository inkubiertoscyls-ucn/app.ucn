"""Rentabilidad por artista: ventas del día de la presentación vs. día normal."""
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.exceptions import ValidationError
from data.ventas import calcular_rentabilidad_artistas
from services.eventos import EventosService

PRODUCTOS = [
    {"id_producto": 1, "nombre_producto": "Pisco Sour", "costo_base": 1000},
    {"id_producto": 2, "nombre_producto": "Papas", "costo_base": None},
]


def _venta(fecha, total, *, producto=1, cantidad=1):
    return {
        "fecha_venta": fecha,
        "total_venta": total,
        "cantidad_total": cantidad,
        "id_producto_relacionado": producto,
    }


def _evento(id_evento, fecha, artista="Trío Azul", costo=50_000, **extra):
    return {
        "id_evento": id_evento,
        "nombre_evento": f"Evento {id_evento}",
        "nombre_artista": artista,
        "costo_artista": costo,
        "fecha_evento": fecha,
        "activo": True,
        **extra,
    }


# Día normal: 2 días sin evento con utilidad 20.000 y 40.000 (promedio 30.000).
VENTAS_NORMALES = [
    _venta("2026-10-01", 30_000, cantidad=10),  # costo 10.000 → utilidad 20.000
    _venta("2026-10-02", 50_000, cantidad=10),  # costo 10.000 → utilidad 40.000
]


def test_ganancia_del_dia_y_frente_a_dia_normal():
    ventas = VENTAS_NORMALES + [
        _venta("2026-10-10", 150_000, cantidad=20),  # costo 20.000 → utilidad 130.000
    ]
    resultado = calcular_rentabilidad_artistas(
        ventas, PRODUCTOS, [_evento(1, "2026-10-10")], hoy="2026-11-01"
    )

    visita = resultado["visitas"][0]
    assert visita["estado"] == "calculado"
    assert visita["ventas"] == 150_000
    assert visita["utilidad_bruta"] == 130_000
    assert visita["ganancia_dia"] == 80_000  # 130.000 - 50.000
    # Día normal: ventas promedio 40.000, utilidad promedio 30.000
    assert resultado["promedio_ventas_dia_normal"] == 40_000
    assert visita["aporte_ventas"] == 110_000
    assert visita["ganancia_vs_normal"] == 50_000  # (130.000 - 30.000) - 50.000
    assert resultado["dias_normales"] == 2


def test_artista_que_no_cubre_su_costo_da_ganancia_negativa():
    ventas = VENTAS_NORMALES + [_venta("2026-10-10", 31_000, cantidad=1)]
    resultado = calcular_rentabilidad_artistas(
        ventas, PRODUCTOS, [_evento(1, "2026-10-10", costo=100_000)], hoy="2026-11-01"
    )
    visita = resultado["visitas"][0]
    assert visita["ganancia_dia"] == -70_000
    assert visita["ganancia_vs_normal"] < visita["ganancia_dia"]


def test_varias_visitas_se_suman_por_artista():
    ventas = VENTAS_NORMALES + [
        _venta("2026-10-10", 100_000, cantidad=10),
        _venta("2026-10-20", 60_000, cantidad=10),
        _venta("2026-10-15", 90_000, cantidad=10),
    ]
    eventos = [
        _evento(1, "2026-10-10", artista="Trío Azul"),
        _evento(2, "2026-10-20", artista="Trío Azul"),
        _evento(3, "2026-10-15", artista="DJ Sur", costo=20_000),
    ]
    resultado = calcular_rentabilidad_artistas(ventas, PRODUCTOS, eventos, hoy="2026-11-01")

    trio = next(f for f in resultado["por_artista"] if f["artista"] == "Trío Azul")
    assert trio["visitas"] == 2
    assert trio["ventas"] == 160_000
    assert trio["ganancia_dia"] == (90_000 - 50_000) + (50_000 - 50_000)
    assert trio["promedio_por_visita"] == 20_000
    assert trio["ultima_fecha"] == "2026-10-20"
    # Ordenado por ganancia del día: DJ Sur (80.000 - 20.000 = 60.000) primero
    assert resultado["por_artista"][0]["artista"] == "DJ Sur"


def test_dia_compartido_reparte_las_ventas():
    ventas = VENTAS_NORMALES + [_venta("2026-10-10", 100_000, cantidad=10)]
    eventos = [
        _evento(1, "2026-10-10", artista="A", costo=0),
        _evento(2, "2026-10-10", artista="B", costo=0),
    ]
    resultado = calcular_rentabilidad_artistas(ventas, PRODUCTOS, eventos, hoy="2026-11-01")
    assert [v["ventas"] for v in resultado["visitas"]] == [50_000, 50_000]
    assert all(v["comparte_dia"] == 2 for v in resultado["visitas"])


def test_ventas_sin_costo_suman_ventas_pero_no_utilidad():
    ventas = VENTAS_NORMALES + [
        _venta("2026-10-10", 100_000, cantidad=10),
        _venta("2026-10-10", 25_000, producto=2),  # sin costo base
        _venta("2026-10-10", 5_000, producto=None),  # sin vincular
    ]
    resultado = calcular_rentabilidad_artistas(
        ventas, PRODUCTOS, [_evento(1, "2026-10-10")], hoy="2026-11-01"
    )
    visita = resultado["visitas"][0]
    assert visita["ventas"] == 130_000
    assert visita["utilidad_bruta"] == 90_000
    assert visita["monto_sin_costo"] == 30_000
    assert visita["parcial"] is True


def test_estados_programado_sin_ventas_y_sin_fecha():
    eventos = [
        _evento(1, "2026-12-24"),  # futuro
        _evento(2, "2026-10-05"),  # sin ventas importadas ese día
        _evento(3, None),  # sin fecha
    ]
    resultado = calcular_rentabilidad_artistas(
        VENTAS_NORMALES, PRODUCTOS, eventos, hoy="2026-11-01"
    )
    estados = {v["id_evento"]: v["estado"] for v in resultado["visitas"]}
    assert estados == {1: "programado", 2: "sin_ventas"}
    assert resultado["eventos_sin_fecha"] == 1
    assert resultado["visitas_calculadas"] == 0
    assert resultado["ganancia_dia_total"] is None


def test_periodo_filtra_eventos_y_dias_con_evento_no_son_normales():
    ventas = VENTAS_NORMALES + [
        _venta("2026-09-15", 999_000, cantidad=1),  # día de un evento fuera del período
        _venta("2026-10-10", 100_000, cantidad=10),
    ]
    eventos = [_evento(1, "2026-10-10"), _evento(2, "2026-09-15")]
    resultado = calcular_rentabilidad_artistas(
        ventas, PRODUCTOS, eventos, desde="2026-10-01", hasta="2026-10-31", hoy="2026-11-01"
    )
    assert [v["id_evento"] for v in resultado["visitas"]] == [1]
    # El 15/09 tuvo evento: no cuenta como día normal aunque esté en las ventas.
    assert resultado["dias_normales"] == 2


def test_sin_dias_normales_no_inventa_comparacion():
    ventas = [_venta("2026-10-10", 100_000, cantidad=10)]
    resultado = calcular_rentabilidad_artistas(
        ventas, PRODUCTOS, [_evento(1, "2026-10-10")], hoy="2026-11-01"
    )
    visita = resultado["visitas"][0]
    assert visita["ganancia_dia"] == 40_000
    assert visita["ganancia_vs_normal"] is None
    assert resultado["ganancia_vs_normal_total"] is None


def test_columna_no_disponible_antes_de_la_migracion():
    evento = _evento(1, None)
    evento.pop("fecha_evento")
    resultado = calcular_rentabilidad_artistas(VENTAS_NORMALES, PRODUCTOS, [evento])
    assert resultado["columna_disponible"] is False


# --- Servicio de eventos ------------------------------------------------------

@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("2026-11-20", "2026-11-20"),
        ("20/11/2026", "2026-11-20"),
        (date(2026, 11, 20), "2026-11-20"),
        ("", None),
        (None, None),
    ],
)
def test_fecha_evento_se_normaliza(valor, esperado):
    assert EventosService._fecha_opcional(valor) == esperado


def test_fecha_evento_invalida_se_rechaza():
    with pytest.raises(ValidationError):
        EventosService._fecha_opcional("31/02/2026")


def test_registrar_evento_guarda_la_fecha():
    servicio = EventosService.__new__(EventosService)

    class Repo:
        def create(self, datos):
            self.creado = datos
            return datos

    servicio.repo = Repo()
    servicio.registrar_evento(
        {
            "nombre_evento": "Noche de jazz",
            "nombre_artista": "Trío Azul",
            "tipo_evento": "Música en Vivo",
            "costo_artista": 50000,
            "fecha_evento": date(2026, 12, 5),
        }
    )
    assert servicio.repo.creado["fecha_evento"] == "2026-12-05"


# --- Interfaz -----------------------------------------------------------------

ADMIN = {
    "rut_usuario": "111111111",
    "nombre_usuario": "Admin",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
}


def _app_rentabilidad(monkeypatch, artistas):
    import views.rentabilidad as vista

    resumen = {
        "con_datos": True,
        "total_registros": 3,
        "ventas_totales": 230_000,
        "artistas": artistas,
    }
    monkeypatch.setattr(vista, "listar_eventos", lambda **_: [])
    monkeypatch.setattr(vista, "resumen_rentabilidad", lambda **_: resumen)

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30
    )
    app.session_state["logged_in"] = True
    app.session_state["user"] = ADMIN
    app.session_state["page"] = "rentabilidad"
    return app.run()


def test_vista_muestra_rentabilidad_por_artista(monkeypatch):
    ventas = VENTAS_NORMALES + [_venta("2026-10-10", 150_000, cantidad=20)]
    artistas = calcular_rentabilidad_artistas(
        ventas, PRODUCTOS, [_evento(1, "2026-10-10")], hoy="2026-11-01"
    )
    app = _app_rentabilidad(monkeypatch, artistas)

    assert not app.exception
    contenido = "\n".join(str(item.value) for item in app.markdown)
    assert "Rentabilidad por artista" in contenido
    assert "Trío Azul" in contenido
    assert "10/10/2026" in contenido
    assert "+$80.000" in contenido  # ganancia del día
    assert "+$50.000" in contenido  # ganancia vs. día normal


def test_vista_pide_migracion_si_falta_la_columna(monkeypatch):
    artistas = calcular_rentabilidad_artistas([], [], [{"id_evento": 1}])
    app = _app_rentabilidad(monkeypatch, artistas)

    assert not app.exception
    assert any("006_add_fecha_evento.sql" in str(aviso.value) for aviso in app.warning)
