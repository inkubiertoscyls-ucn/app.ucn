"""Pruebas del módulo de Proveedores.

Se usan repositorios y servicios dobles. Ninguna prueba escribe en Supabase.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.exceptions import (
    AuthorizationError,
    DuplicateError,
    NotFoundError,
    SupabaseConnectionError,
    ValidationError,
)
from data.errors import CONEXION, ErrorDatos
from data.proveedores import (
    cambiar_estado_proveedor,
    listar_proveedores_admin,
    registrar_proveedor,
)
from services.proveedores import ProveedoresService
from views import proveedores as vista_proveedores
from views.proveedores import (
    _metricas,
    _tabla_proveedores,
    filtrar_proveedores,
)

ADMIN = {
    "rut_usuario": "12345678-5",
    "nombre_usuario": "Ana Admin",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
}
OPERARIO = {
    "rut_usuario": "11111111-1",
    "nombre_usuario": "Beto Operario",
    "rol": "Operario",
    "area_asignada": "Barra",
    "activo": True,
}
PROVEEDOR = {
    "rut_proveedor": "123456785",
    "nombre_proveedor": "Distribuidora Central",
    "contacto_proveedor": "ventas@central.cl",
    "tipo_proveedor": "Insumos",
    "activo": True,
}
PROVEEDOR_INACTIVO = {
    "rut_proveedor": "222222222",
    "nombre_proveedor": "Bebidas del Sur",
    "contacto_proveedor": "+56 9 1234 5678",
    "tipo_proveedor": "Bebidas",
    "activo": False,
}


class FakeProveedoresRepo:
    """Repositorio en memoria para probar las reglas del servicio."""

    def __init__(self, proveedores=None):
        self.proveedores = {
            str(fila["rut_proveedor"]): dict(fila) for fila in proveedores or []
        }
        self.creados = []
        self.updates = []
        self.deactivations = []

    def get_by_rut_estricto(self, rut):
        fila = self.proveedores.get(str(rut))
        return dict(fila) if fila else None

    def existe_rut(self, rut):
        return str(rut) in self.proveedores

    def get_activos(self):
        return [dict(fila) for fila in self.proveedores.values() if fila.get("activo")]

    def get_all(self):
        return [dict(fila) for fila in self.proveedores.values()]

    def buscar_estricto(self, termino):
        buscado = str(termino).casefold()
        return [
            dict(fila)
            for fila in self.proveedores.values()
            if any(
                buscado in str(fila.get(campo) or "").casefold()
                for campo in (
                    "nombre_proveedor",
                    "rut_proveedor",
                    "contacto_proveedor",
                    "tipo_proveedor",
                )
            )
        ]

    def create(self, data):
        nuevo = dict(data)
        self.proveedores[str(nuevo["rut_proveedor"])] = nuevo
        self.creados.append(nuevo)
        return dict(nuevo)

    def update(self, id_column, id_value, data):
        fila = self.proveedores[str(id_value)]
        fila.update(data)
        self.updates.append((str(id_value), dict(data)))
        return dict(fila)

    def deactivate(self, id_column, id_value):
        return self.update(id_column, id_value, {"activo": False})


def _servicio(proveedores=None):
    servicio = ProveedoresService()
    servicio.repo = FakeProveedoresRepo(proveedores)
    return servicio


class FakeProveedoresService:
    """Servicio doble para la capa de datos."""

    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.solo_activos = None
        self.registrados = []
        self.estados = []

    def listar_proveedores(self, solo_activos=False):
        self.solo_activos = solo_activos
        if self.error:
            raise self.error
        return self.filas

    def registrar_proveedor(self, data):
        if self.error:
            raise self.error
        self.registrados.append(dict(data))
        return dict(data)

    def activar_proveedor(self, rut):
        self.estados.append((str(rut), True))
        return {"rut_proveedor": rut, "activo": True}

    def desactivar_proveedor(self, rut):
        self.estados.append((str(rut), False))
        return {"rut_proveedor": rut, "activo": False}


class TestServicioProveedores:
    def test_registrar_proveedor_normaliza_rut(self):
        servicio = _servicio()

        creado = servicio.registrar_proveedor(
            {
                "rut_proveedor": " 12.345.678-5 ",
                "nombre_proveedor": "  Distribuidora Central  ",
                "contacto_proveedor": " ventas@central.cl ",
                "tipo_proveedor": " Insumos ",
            }
        )

        assert creado["rut_proveedor"] == "123456785"
        assert creado["nombre_proveedor"] == "Distribuidora Central"
        assert creado["contacto_proveedor"] == "ventas@central.cl"
        assert creado["tipo_proveedor"] == "Insumos"
        assert creado["activo"] is True
        assert len(servicio.repo.creados) == 1

    @pytest.mark.parametrize(
        "cambios,mensaje",
        [
            ({"rut_proveedor": ""}, "rut"),
            ({"rut_proveedor": "12345678-0"}, "rut"),
            ({"nombre_proveedor": ""}, "nombre"),
            ({"nombre_proveedor": "A"}, "al menos 2"),
        ],
    )
    def test_rechaza_datos_invalidos(self, cambios, mensaje):
        servicio = _servicio()
        datos = {
            "rut_proveedor": "12345678-5",
            "nombre_proveedor": "Distribuidora Central",
            **cambios,
        }

        with pytest.raises(ValidationError) as info:
            servicio.registrar_proveedor(datos)

        assert mensaje in str(info.value).lower()

    def test_rechaza_rut_duplicado(self):
        servicio = _servicio([PROVEEDOR])

        with pytest.raises(DuplicateError):
            servicio.registrar_proveedor(
                {
                    "rut_proveedor": "12.345.678-5",
                    "nombre_proveedor": "Otro proveedor",
                }
            )

    def test_modificar_conserva_el_rut(self):
        servicio = _servicio([PROVEEDOR])

        actualizado = servicio.modificar_proveedor(
            "123456785", {"nombre_proveedor": "Central Mayorista"}
        )

        assert actualizado["nombre_proveedor"] == "Central Mayorista"
        assert actualizado["rut_proveedor"] == "123456785"
        assert servicio.repo.updates == [
            ("123456785", {"nombre_proveedor": "Central Mayorista"})
        ]

    def test_no_permite_cambiar_el_rut(self):
        servicio = _servicio([PROVEEDOR])

        with pytest.raises(ValidationError) as info:
            servicio.modificar_proveedor(
                "123456785",
                {"rut_proveedor": "22222222-2", "nombre_proveedor": "Cambio"},
            )

        assert "no se puede modificar" in str(info.value).lower()
        assert servicio.repo.updates == []

    def test_permite_enviar_el_mismo_rut_en_edicion(self):
        servicio = _servicio([PROVEEDOR])

        actualizado = servicio.modificar_proveedor(
            "123456785",
            {
                "rut_proveedor": "12.345.678-5",
                "nombre_proveedor": "Central",
            },
        )

        assert actualizado["nombre_proveedor"] == "Central"
        assert servicio.repo.updates == [
            ("123456785", {"nombre_proveedor": "Central"})
        ]

    def test_activar_y_desactivar_proveedor(self):
        servicio = _servicio([PROVEEDOR, PROVEEDOR_INACTIVO])

        activado = servicio.activar_proveedor("222222222")
        desactivado = servicio.desactivar_proveedor("123456785")

        assert activado["activo"] is True
        assert desactivado["activo"] is False
        assert servicio.repo.updates == [
            ("222222222", {"activo": True}),
            ("123456785", {"activo": False}),
        ]

    def test_proveedor_inexistente(self):
        servicio = _servicio()

        with pytest.raises(NotFoundError):
            servicio.modificar_proveedor("123456785", {"nombre_proveedor": "Otro"})

    def test_busqueda_corta_se_rechaza(self):
        servicio = _servicio([PROVEEDOR])

        with pytest.raises(ValidationError):
            servicio.buscar_proveedores("a")


class TestDataProveedores:
    def test_listar_admin_exige_permisos(self, monkeypatch):
        servicio = FakeProveedoresService([PROVEEDOR])
        monkeypatch.setattr("data.proveedores.ProveedoresService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            listar_proveedores_admin(usuario=OPERARIO)

        assert servicio.solo_activos is None

    def test_listar_admin_incluye_inactivos(self, monkeypatch):
        servicio = FakeProveedoresService([PROVEEDOR, PROVEEDOR_INACTIVO])
        monkeypatch.setattr("data.proveedores.ProveedoresService", lambda: servicio)

        filas = listar_proveedores_admin(usuario=ADMIN)

        assert len(filas) == 2
        assert servicio.solo_activos is False

    def test_registrar_invalida_cache(self, monkeypatch):
        servicio = FakeProveedoresService()
        monkeypatch.setattr("data.proveedores.ProveedoresService", lambda: servicio)
        limpiezas = []
        monkeypatch.setattr(
            "data.proveedores.limpiar_cache", lambda: limpiezas.append(True)
        )

        registrar_proveedor(
            {"rut_proveedor": "12345678-5", "nombre_proveedor": "Central"},
            usuario=ADMIN,
        )

        assert len(servicio.registrados) == 1
        assert limpiezas == [True]

    def test_cambiar_estado_exige_permisos(self, monkeypatch):
        servicio = FakeProveedoresService()
        monkeypatch.setattr("data.proveedores.ProveedoresService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            cambiar_estado_proveedor("123456785", False, usuario=OPERARIO)

        assert servicio.estados == []

    def test_error_de_conexion_se_traduce(self, monkeypatch):
        servicio = FakeProveedoresService(error=SupabaseConnectionError("sin red"))
        monkeypatch.setattr("data.proveedores.ProveedoresService", lambda: servicio)

        with pytest.raises(ErrorDatos) as info:
            listar_proveedores_admin(usuario=ADMIN)

        assert info.value.tipo == CONEXION


class TestVistaProveedores:
    def test_filtrar_por_texto_rut_tipo_y_estado(self):
        proveedores = [PROVEEDOR, PROVEEDOR_INACTIVO]

        assert [
            fila["rut_proveedor"]
            for fila in filtrar_proveedores(proveedores, texto="central")
        ] == ["123456785"]
        assert [
            fila["rut_proveedor"]
            for fila in filtrar_proveedores(proveedores, texto="12.345.678-5")
        ] == ["123456785"]
        assert [
            fila["rut_proveedor"]
            for fila in filtrar_proveedores(proveedores, tipo="Bebidas")
        ] == ["222222222"]
        assert [
            fila["rut_proveedor"]
            for fila in filtrar_proveedores(proveedores, estado="Activos")
        ] == ["123456785"]
        assert [
            fila["rut_proveedor"]
            for fila in filtrar_proveedores(proveedores, estado="Inactivos")
        ] == ["222222222"]

    def test_tabla_muestra_rut_formateado_y_estado(self):
        html = _tabla_proveedores([PROVEEDOR, PROVEEDOR_INACTIVO])

        assert "Distribuidora Central" in html
        assert "Bebidas del Sur" in html
        assert "12.345.678-5" in html
        assert "Activo" in html
        assert "Inactivo" in html
        assert "Contacto" in html

    def test_metricas_no_pasa_argumentos_no_soportados(self, monkeypatch):
        llamadas = []

        def falso_metric_grid(items, **kwargs):
            llamadas.append((list(items), kwargs))

        monkeypatch.setattr(vista_proveedores, "metric_grid", falso_metric_grid)

        _metricas([PROVEEDOR, PROVEEDOR_INACTIVO])

        assert len(llamadas) == 1
        items, kwargs = llamadas[0]
        assert len(items) == 4
        assert kwargs == {}


def _app_proveedores(monkeypatch, filas, usuario):
    monkeypatch.setattr(
        vista_proveedores,
        "listar_proveedores_admin",
        lambda usuario=None: filas,
    )
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=30,
    )
    app.session_state["logged_in"] = True
    app.session_state["user"] = usuario
    app.session_state["page"] = "proveedores"
    app.run()
    return app


class TestInterfazProveedores:
    def test_admin_ve_catalogo_y_formulario(self, monkeypatch):
        app = _app_proveedores(
            monkeypatch, [PROVEEDOR, PROVEEDOR_INACTIVO], ADMIN
        )

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Distribuidora Central" in contenido
        assert "Bebidas del Sur" in contenido
        assert "ink-metrics--4" in contenido
        assert "Registrar proveedor" in contenido
        assert any(
            campo.label == "RUT del proveedor" for campo in app.text_input
        )

    def test_catalogo_vacio_permite_crear_el_primero(self, monkeypatch):
        app = _app_proveedores(monkeypatch, [], ADMIN)

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Aún no hay proveedores registrados" in contenido
        assert any(
            campo.label == "RUT del proveedor" for campo in app.text_input
        )

    def test_operario_no_accede_a_proveedores(self, monkeypatch):
        def prohibido(usuario=None):
            raise AssertionError("La capa de datos no debe consultarse")

        monkeypatch.setattr(vista_proveedores, "listar_proveedores_admin", prohibido)
        app = _app_proveedores(monkeypatch, [], OPERARIO)

        assert not app.exception
        assert any("permisos" in str(error.value) for error in app.error)
