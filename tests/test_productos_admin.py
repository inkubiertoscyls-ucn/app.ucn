"""Pruebas del módulo de Productos.

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
from data.productos import (
    cambiar_estado_producto,
    listar_productos_admin,
    registrar_producto,
)
from services.productos import ProductosService
from views import productos as vista_productos
from views.productos import (
    _metricas,
    _tabla_productos,
    filtrar_productos,
)

ADMIN = {
    "rut_usuario": "12345678-9",
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
PRODUCTO = {
    "id_producto": 1,
    "nombre_producto": "Tomate",
    "categoria": "Verduras",
    "unidad_medida": "KG",
    "costo_base": 1200,
    "stock_minimo": 5,
    "stock_maximo": 20,
    "activo": True,
}
PRODUCTO_INACTIVO = {
    "id_producto": 2,
    "nombre_producto": "Harina",
    "categoria": "Insumos",
    "unidad_medida": "KG",
    "costo_base": 900,
    "stock_minimo": 2,
    "stock_maximo": 10,
    "activo": False,
}


class FakeProductosRepo:
    """Repositorio en memoria para probar las reglas del servicio."""

    def __init__(self, productos=None):
        self.productos = {
            int(fila["id_producto"]): dict(fila) for fila in productos or []
        }
        self.creados = []
        self.updates = []
        self.deactivations = []

    def get_by_id_estricto(self, id_producto):
        fila = self.productos.get(int(id_producto))
        return dict(fila) if fila else None

    def get_by_nombre_estricto(self, nombre):
        buscado = str(nombre).strip().casefold()
        for fila in self.productos.values():
            if str(fila.get("nombre_producto") or "").strip().casefold() == buscado:
                return dict(fila)
        return None

    def existe_nombre(self, nombre, exclude_id=None):
        encontrado = self.get_by_nombre_estricto(nombre)
        if not encontrado:
            return False
        return int(encontrado["id_producto"]) != int(exclude_id or 0)

    def get_activos(self):
        return [dict(fila) for fila in self.productos.values() if fila.get("activo")]

    def get_all(self):
        return [dict(fila) for fila in self.productos.values()]

    def create(self, data):
        nuevo = dict(data)
        nuevo["id_producto"] = max(self.productos, default=0) + 1
        self.productos[nuevo["id_producto"]] = nuevo
        self.creados.append(nuevo)
        return dict(nuevo)

    def update(self, id_column, id_value, data):
        fila = self.productos[int(id_value)]
        fila.update(data)
        self.updates.append((int(id_value), dict(data)))
        return dict(fila)

    def deactivate(self, id_column, id_value):
        return self.update(id_column, id_value, {"activo": False})


def _servicio(productos=None):
    servicio = ProductosService()
    servicio.repo = FakeProductosRepo(productos)
    return servicio


class FakeProductosService:
    """Servicio doble para la capa de datos."""

    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.solo_activos = None
        self.registrados = []
        self.estados = []

    def listar_productos(self, solo_activos=True):
        self.solo_activos = solo_activos
        if self.error:
            raise self.error
        return self.filas

    def registrar_producto(self, data):
        if self.error:
            raise self.error
        self.registrados.append(dict(data))
        return {"id_producto": 9, **data}

    def activar_producto(self, id_producto):
        self.estados.append((int(id_producto), True))
        return {"id_producto": id_producto, "activo": True}

    def desactivar_producto(self, id_producto):
        self.estados.append((int(id_producto), False))
        return {"id_producto": id_producto, "activo": False}


class TestServicioProductos:
    def test_registrar_producto_valido_no_crea_stock(self):
        servicio = _servicio()

        creado = servicio.registrar_producto(
            {
                "nombre_producto": "  Tomate  ",
                "categoria": " Verduras ",
                "unidad_medida": " KG ",
                "costo_base": "1200",
                "stock_minimo": "5",
                "stock_maximo": "20",
            }
        )

        assert creado["nombre_producto"] == "Tomate"
        assert creado["categoria"] == "Verduras"
        assert creado["unidad_medida"] == "KG"
        assert creado["costo_base"] == 1200.0
        assert creado["stock_minimo"] == 5.0
        assert creado["stock_maximo"] == 20.0
        assert creado["activo"] is True
        assert len(servicio.repo.creados) == 1

    @pytest.mark.parametrize(
        "cambios,mensaje",
        [
            ({"nombre_producto": ""}, "nombre"),
            ({"nombre_producto": "A"}, "al menos 2"),
            ({"unidad_medida": ""}, "unidad"),
            ({"costo_base": -1}, "negativo"),
            ({"stock_minimo": -1}, "negativo"),
            ({"stock_maximo": -1}, "negativo"),
            ({"stock_minimo": 10, "stock_maximo": 5}, "máximo"),
            ({"costo_base": "abc"}, "número"),
        ],
    )
    def test_rechaza_datos_invalidos(self, cambios, mensaje):
        servicio = _servicio()
        datos = {
            "nombre_producto": "Tomate",
            "unidad_medida": "KG",
            "costo_base": 1000,
            "stock_minimo": 1,
            "stock_maximo": 10,
            **cambios,
        }

        with pytest.raises(ValidationError) as info:
            servicio.registrar_producto(datos)

        assert mensaje in str(info.value).lower()

    def test_rechaza_nombre_duplicado_sin_importar_mayusculas(self):
        servicio = _servicio([PRODUCTO])

        with pytest.raises(DuplicateError):
            servicio.registrar_producto(
                {"nombre_producto": "tomate", "unidad_medida": "KG"}
            )

    def test_modificar_solo_el_nombre_conserva_stock(self):
        servicio = _servicio([PRODUCTO])

        actualizado = servicio.modificar_producto(1, {"nombre_producto": "Tomate pera"})

        assert actualizado["nombre_producto"] == "Tomate pera"
        assert actualizado["stock_minimo"] == 5
        assert actualizado["stock_maximo"] == 20
        assert servicio.repo.updates[0][1] == {"nombre_producto": "Tomate pera"}

    def test_modificar_stock_minimo_valida_el_maximo_actual(self):
        servicio = _servicio([PRODUCTO])

        with pytest.raises(ValidationError):
            servicio.modificar_producto(1, {"stock_minimo": 30})

    def test_activar_y_desactivar_producto(self):
        servicio = _servicio([PRODUCTO, PRODUCTO_INACTIVO])

        activado = servicio.activar_producto(2)
        desactivado = servicio.desactivar_producto(1)

        assert activado["activo"] is True
        assert desactivado["activo"] is False
        assert servicio.repo.updates == [
            (2, {"activo": True}),
            (1, {"activo": False}),
        ]

    def test_producto_inexistente(self):
        servicio = _servicio()

        with pytest.raises(NotFoundError):
            servicio.modificar_producto(99, {"nombre_producto": "Otro"})

    def test_identificador_invalido(self):
        servicio = _servicio()

        with pytest.raises(ValidationError):
            servicio.consultar_producto("abc")


class TestDataProductos:
    def test_listar_admin_exige_permisos(self, monkeypatch):
        servicio = FakeProductosService([PRODUCTO])
        monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            listar_productos_admin(usuario=OPERARIO)

        assert servicio.solo_activos is None

    def test_listar_admin_incluye_inactivos(self, monkeypatch):
        servicio = FakeProductosService([PRODUCTO, PRODUCTO_INACTIVO])
        monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)

        filas = listar_productos_admin(usuario=ADMIN)

        assert len(filas) == 2
        assert servicio.solo_activos is False

    def test_registrar_invalida_cache(self, monkeypatch):
        servicio = FakeProductosService()
        monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)
        limpiezas = []
        monkeypatch.setattr("data.productos.limpiar_cache", lambda: limpiezas.append(True))

        registrar_producto(
            {"nombre_producto": "Tomate", "unidad_medida": "KG"},
            usuario=ADMIN,
        )

        assert len(servicio.registrados) == 1
        assert limpiezas == [True]

    def test_cambiar_estado_exige_permisos(self, monkeypatch):
        servicio = FakeProductosService()
        monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            cambiar_estado_producto(1, False, usuario=OPERARIO)

        assert servicio.estados == []

    def test_error_de_conexion_se_traduce(self, monkeypatch):
        servicio = FakeProductosService(error=SupabaseConnectionError("sin red"))
        monkeypatch.setattr("data.productos.ProductosService", lambda: servicio)

        with pytest.raises(ErrorDatos) as info:
            listar_productos_admin(usuario=ADMIN)

        assert info.value.tipo == CONEXION


class TestVistaProductos:
    def test_filtrar_por_texto_categoria_y_estado(self):
        productos = [PRODUCTO, PRODUCTO_INACTIVO]

        assert [fila["id_producto"] for fila in filtrar_productos(productos, texto="tomate")] == [1]
        assert [fila["id_producto"] for fila in filtrar_productos(productos, categoria="Insumos")] == [2]
        assert [fila["id_producto"] for fila in filtrar_productos(productos, estado="Activos")] == [1]
        assert [fila["id_producto"] for fila in filtrar_productos(productos, estado="Inactivos")] == [2]

    def test_tabla_muestra_estado_y_stock(self):
        html = _tabla_productos([PRODUCTO, PRODUCTO_INACTIVO])

        assert "Tomate" in html
        assert "Harina" in html
        assert "Activo" in html
        assert "Inactivo" in html
        assert "Stock mínimo" in html
        assert "Stock máximo" in html

    def test_metricas_no_pasa_argumentos_no_soportados(self, monkeypatch):
        llamadas = []

        def falso_metric_grid(items, **kwargs):
            llamadas.append((list(items), kwargs))

        monkeypatch.setattr(vista_productos, "metric_grid", falso_metric_grid)

        _metricas([PRODUCTO, PRODUCTO_INACTIVO])

        assert len(llamadas) == 1
        items, kwargs = llamadas[0]
        assert len(items) == 4
        assert kwargs == {}


def _app_productos(monkeypatch, filas, usuario):
    monkeypatch.setattr(
        vista_productos,
        "listar_productos_admin",
        lambda usuario=None: filas,
    )
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=30,
    )
    app.session_state["logged_in"] = True
    app.session_state["user"] = usuario
    app.session_state["page"] = "productos"
    app.run()
    return app


class TestInterfazProductos:
    def test_admin_ve_catalogo_y_formulario(self, monkeypatch):
        app = _app_productos(monkeypatch, [PRODUCTO, PRODUCTO_INACTIVO], ADMIN)

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Tomate" in contenido
        assert "Harina" in contenido
        assert "ink-metrics--4" in contenido
        assert "Registrar producto" in contenido
        assert any(
            campo.label == "Nombre del producto" for campo in app.text_input
        )

    def test_catalogo_vacio_permite_crear_el_primero(self, monkeypatch):
        app = _app_productos(monkeypatch, [], ADMIN)

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Aún no hay productos registrados" in contenido
        assert any(
            campo.label == "Nombre del producto" for campo in app.text_input
        )

    def test_operario_no_accede_a_productos(self, monkeypatch):
        def prohibido(usuario=None):
            raise AssertionError("La capa de datos no debe consultarse")

        monkeypatch.setattr(vista_productos, "listar_productos_admin", prohibido)
        app = _app_productos(monkeypatch, [], OPERARIO)

        assert not app.exception
        assert any("permisos" in str(error.value) for error in app.error)
