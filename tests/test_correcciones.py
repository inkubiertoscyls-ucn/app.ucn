"""Pruebas de las correcciones de la revisión (zona horaria, login, stock, formato)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from core import intentos_login
from core.exceptions import NegativeStockError
from core.tiempo import ZONA_CHILE, a_hora_chile, marca_tiempo
from core.utils import formatear_rut, validar_rut
from services.fudo_import import _hash_canonico
from services.inventario import InventarioService
from ui.format import fmt_clp, fmt_fecha_hora


# --- Zona horaria -----------------------------------------------------------

def test_marca_tiempo_incluye_desfase_de_chile():
    texto = marca_tiempo()
    fecha = datetime.fromisoformat(texto)
    assert fecha.tzinfo is not None
    assert fecha.utcoffset() == datetime.now(ZONA_CHILE).utcoffset()


def test_hora_utc_se_muestra_en_hora_de_chile():
    utc = datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc)  # verano: UTC-3
    assert a_hora_chile(utc).hour == 12
    assert fmt_fecha_hora("2026-01-15T15:00:00+00:00") == "15/01/2026 12:00"


def test_hora_sin_zona_se_considera_hora_de_chile():
    assert fmt_fecha_hora("2026-01-15T15:00:00") == "15/01/2026 15:00"


# --- Formato de pesos -------------------------------------------------------

@pytest.mark.parametrize(
    "valor, compacto, esperado",
    [
        (1_234_567_890, True, "$1.234,6M"),
        (12_345_678, True, "$12,3M"),
        (-1_234_567, True, "-$1,2M"),
        (5_300, True, "$5K"),
        (-5_300, False, "-$5.300"),
        (0, False, "$0"),
        ("abc", False, "—"),
    ],
)
def test_fmt_clp(valor, compacto, esperado):
    assert fmt_clp(valor, compacto) == esperado


# --- RUT --------------------------------------------------------------------

def test_rut_bajo_el_millon_es_valido():
    assert validar_rut("999.999-K")
    assert formatear_rut("999999k") == "999.999-K"


# --- Límite de intentos de login -------------------------------------------

def test_bloqueo_tras_intentos_fallidos():
    intentos_login.reiniciar()
    rut = "11.111.111-1"
    for _ in range(intentos_login.MAX_INTENTOS - 1):
        intentos_login.registrar_fallo(rut, ahora=100.0)
    assert intentos_login.segundos_bloqueo(rut, ahora=100.0) == 0

    intentos_login.registrar_fallo(rut, ahora=100.0)
    assert intentos_login.segundos_bloqueo("111111111", ahora=101.0) > 0

    pasado = 100.0 + intentos_login.BLOQUEO_SEGUNDOS + 1
    assert intentos_login.segundos_bloqueo(rut, ahora=pasado) == 0
    intentos_login.reiniciar()


def test_ingreso_correcto_limpia_fallos():
    intentos_login.reiniciar()
    rut = "11.111.111-1"
    for _ in range(intentos_login.MAX_INTENTOS - 1):
        intentos_login.registrar_fallo(rut, ahora=50.0)
    intentos_login.registrar_exito(rut)
    intentos_login.registrar_fallo(rut, ahora=51.0)
    assert intentos_login.segundos_bloqueo(rut, ahora=51.0) == 0
    intentos_login.reiniciar()


# --- FUDO: duplicados -------------------------------------------------------

def test_hash_sin_referencia_es_compatible_con_el_anterior():
    base = _hash_canonico("2026-11-01", 5000.0, 2.0, "Burger")
    assert base == _hash_canonico("2026-11-01", 5000.0, 2.0, "Burger", "")
    assert base != _hash_canonico("2026-11-01", 5000.0, 2.0, "Burger", "ticket 15")


# --- Stock: movimientos simultáneos -----------------------------------------

def _servicio_con_stock(stocks):
    servicio = InventarioService.__new__(InventarioService)
    servicio._validar_movimiento_base = MagicMock()
    servicio._resolver_id_fecha = MagicMock()
    servicio.tipos_mov_repo = MagicMock()
    servicio.tipos_mov_repo.get_by_id.return_value = {"factor_stock": -1}
    servicio.movimientos_repo = MagicMock()
    servicio.movimientos_repo.create.return_value = {"id_hecho_inventario": 77}
    servicio.calcular_stock_actual = MagicMock(side_effect=stocks)
    return servicio


def _salida():
    return {"id_producto": 1, "id_area": 1, "id_tipo_movimiento": 2, "cantidad": 3}


def test_salida_revierte_si_otro_usuario_dejo_stock_negativo():
    # Antes de insertar hay 5; después de insertar quedó -1 por otra salida.
    servicio = _servicio_con_stock([5, -1])
    with pytest.raises(NegativeStockError):
        servicio.registrar_salida(_salida())
    servicio.movimientos_repo.delete.assert_called_once_with("id_hecho_inventario", 77)


def test_salida_normal_no_se_revierte():
    servicio = _servicio_con_stock([5, 2])
    resultado = servicio.registrar_salida(_salida())
    assert resultado == {"id_hecho_inventario": 77}
    servicio.movimientos_repo.delete.assert_not_called()


def test_salida_sin_stock_no_inserta():
    servicio = _servicio_con_stock([2])
    with pytest.raises(NegativeStockError):
        servicio.registrar_salida(_salida())
    servicio.movimientos_repo.create.assert_not_called()


def test_error_de_conexion_no_se_convierte_en_stock_cero():
    servicio = InventarioService.__new__(InventarioService)
    servicio.movimientos_repo = MagicMock()
    servicio.movimientos_repo.get_stock_movimientos.side_effect = ConnectionError("sin red")
    with pytest.raises(ConnectionError):
        servicio.calcular_stock_actual(1, 1)


# --- Revalidación de la sesión ---------------------------------------------

@pytest.mark.revalidacion_real
def test_revalidar_detecta_cuenta_desactivada(monkeypatch):
    import ui.state

    repo = MagicMock()
    repo.get_by_rut.return_value = {"rut_usuario": "111111111", "activo": False}
    monkeypatch.setattr("repositories.usuarios.UsuariosRepository", lambda: repo)
    motivo = ui.state._revalidar_usuario({"rut_usuario": "111111111"})
    assert motivo and "desactivada" in motivo


@pytest.mark.revalidacion_real
def test_revalidar_actualiza_rol(monkeypatch):
    import ui.state

    repo = MagicMock()
    repo.get_by_rut.return_value = {
        "rut_usuario": "111111111",
        "nombre_usuario": "Ana",
        "rol": "Operario",
        "area_asignada": "Cocina",
        "activo": True,
    }
    monkeypatch.setattr("repositories.usuarios.UsuariosRepository", lambda: repo)
    usuario = {"rut_usuario": "111111111", "rol": "Administrador"}
    assert ui.state._revalidar_usuario(usuario) is None
    assert usuario["rol"] == "Operario"
    assert usuario["area_asignada"] == "Cocina"


@pytest.mark.revalidacion_real
def test_revalidar_no_expulsa_por_corte_de_red(monkeypatch):
    import ui.state

    repo = MagicMock()
    repo.get_by_rut.side_effect = ConnectionError("sin red")
    monkeypatch.setattr("repositories.usuarios.UsuariosRepository", lambda: repo)
    assert ui.state._revalidar_usuario({"rut_usuario": "111111111"}) is None


# --- Menú lateral -------------------------------------------------------------

def test_menu_inventario_va_despues_de_movimientos_y_antes_de_alertas():
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30
    )
    app.session_state["logged_in"] = True
    app.session_state["user"] = {
        "rut_usuario": "111111111",
        "nombre_usuario": "Operario",
        "rol": "Operario",
        "area_asignada": "Cocina",
        "activo": True,
    }
    # "usuarios" se detiene por permisos antes de consultar datos; el menú
    # lateral se dibuja igual.
    app.session_state["page"] = "usuarios"
    app.run()

    etiquetas = [boton.label for boton in app.sidebar.button]
    assert etiquetas[:4] == ["Inicio", "Movimientos", "Inventario", "Alertas"]
