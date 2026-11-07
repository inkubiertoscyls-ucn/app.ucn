"""Pruebas del módulo de Artistas y Eventos.

Se usan repositorios y servicios dobles. Ninguna prueba escribe en Supabase.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from core.exceptions import (
    AuthorizationError,
    NotFoundError,
    SupabaseConnectionError,
    ValidationError,
)
from data.errors import CONEXION, ErrorDatos
from data.eventos import (
    actividad_eventos_admin,
    cambiar_estado_evento,
    listar_eventos_admin,
    registrar_evento,
)
from repositories.eventos import EventosRepository
from services.eventos import EventosService
from views import eventos as vista_eventos
from views.eventos import (
    _duplicados,
    _metricas,
    _rango_actividad,
    _tabla_eventos,
    agrupar_artistas,
    filtrar_eventos,
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
EVENTO = {
    "id_evento": 1,
    "nombre_evento": "Noche de jazz",
    "nombre_artista": "Trío Azul",
    "tipo_evento": "Concierto",
    "costo_artista": 250000,
    "activo": True,
}
EVENTO_INACTIVO = {
    "id_evento": 2,
    "nombre_evento": "Festival de verano",
    "nombre_artista": "Banda Sur",
    "tipo_evento": "Festival",
    "costo_artista": 500000,
    "activo": False,
}
EVENTO_SIN_ARTISTA = {
    "id_evento": 3,
    "nombre_evento": "Evento privado",
    "nombre_artista": "",
    "tipo_evento": "Privado",
    "costo_artista": 0,
    "activo": True,
}


class FakeEventosRepo:
    """Repositorio en memoria para probar las reglas del servicio."""

    def __init__(self, eventos=None):
        self.eventos = {
            int(fila["id_evento"]): dict(fila) for fila in eventos or []
        }
        self.creados = []
        self.updates = []
        self.actividad = {1: {"primera": "2026-01-10", "ultima": "2026-01-12"}}

    def get_by_id_estricto(self, id_evento):
        fila = self.eventos.get(int(id_evento))
        return dict(fila) if fila else None

    def get_activos(self):
        return [dict(fila) for fila in self.eventos.values() if fila.get("activo")]

    def get_all(self):
        return [dict(fila) for fila in self.eventos.values()]

    def buscar_estricto(self, termino):
        buscado = str(termino).casefold()
        return [
            dict(fila)
            for fila in self.eventos.values()
            if any(
                buscado in str(fila.get(campo) or "").casefold()
                for campo in ("nombre_evento", "nombre_artista", "tipo_evento")
            )
        ]

    def create(self, data):
        nuevo = dict(data)
        nuevo["id_evento"] = max(self.eventos, default=0) + 1
        self.eventos[nuevo["id_evento"]] = nuevo
        self.creados.append(nuevo)
        return dict(nuevo)

    def update(self, id_column, id_value, data):
        fila = self.eventos[int(id_value)]
        fila.update(data)
        self.updates.append((int(id_value), dict(data)))
        return dict(fila)

    def deactivate(self, id_column, id_value):
        return self.update(id_column, id_value, {"activo": False})

    def fechas_actividad(self):
        return self.actividad


def _servicio(eventos=None):
    servicio = EventosService()
    servicio.repo = FakeEventosRepo(eventos)
    return servicio


class FakeEventosService:
    """Servicio doble para la capa de datos."""

    def __init__(self, filas=None, error=None):
        self.filas = filas or []
        self.error = error
        self.solo_activos = None
        self.registrados = []
        self.estados = []

    def listar_eventos(self, solo_activos=False):
        self.solo_activos = solo_activos
        if self.error:
            raise self.error
        return self.filas

    def registrar_evento(self, data):
        if self.error:
            raise self.error
        self.registrados.append(dict(data))
        return {"id_evento": 9, **data}

    def activar_evento(self, id_evento):
        self.estados.append((int(id_evento), True))
        return {"id_evento": id_evento, "activo": True}

    def desactivar_evento(self, id_evento):
        self.estados.append((int(id_evento), False))
        return {"id_evento": id_evento, "activo": False}

    def fechas_actividad(self):
        if self.error:
            raise self.error
        return {1: {"primera": "2026-01-10", "ultima": "2026-01-12"}}


class TestServicioEventos:
    def test_registrar_evento_normaliza_campos(self):
        servicio = _servicio()

        creado = servicio.registrar_evento(
            {
                "nombre_evento": "  Noche de jazz  ",
                "nombre_artista": "  Trío Azul ",
                "tipo_evento": " Concierto ",
                "costo_artista": "250000",
            }
        )

        assert creado["nombre_evento"] == "Noche de jazz"
        assert creado["nombre_artista"] == "Trío Azul"
        assert creado["tipo_evento"] == "Concierto"
        assert creado["costo_artista"] == 250000.0
        assert creado["activo"] is True
        assert len(servicio.repo.creados) == 1

    @pytest.mark.parametrize(
        "cambios,mensaje",
        [
            ({"nombre_evento": ""}, "nombre"),
            ({"nombre_evento": "A"}, "al menos 2"),
            ({"costo_artista": -1}, "negativo"),
            ({"costo_artista": "abc"}, "número"),
            ({"nombre_artista": "A" * 151}, "artista"),
            ({"tipo_evento": "A" * 51}, "tipo"),
            ({"tipo_evento": ""}, "tipo"),
        ],
    )
    def test_rechaza_datos_invalidos(self, cambios, mensaje):
        servicio = _servicio()
        datos = {
            "nombre_evento": "Noche de jazz",
            "nombre_artista": "Trío Azul",
            "tipo_evento": "Concierto",
            "costo_artista": 1000,
            **cambios,
        }

        with pytest.raises(ValidationError) as info:
            servicio.registrar_evento(datos)

        assert mensaje in str(info.value).lower()

    def test_no_bloquea_nombres_duplicados(self):
        servicio = _servicio([EVENTO])

        creado = servicio.registrar_evento(
            {
                "nombre_evento": "Noche de jazz",
                "nombre_artista": "Otra banda",
                "tipo_evento": "Concierto",
            }
        )

        assert creado["nombre_evento"] == "Noche de jazz"
        assert len(servicio.repo.creados) == 1

    def test_modificar_solo_nombre_conserva_artista_y_costo(self):
        servicio = _servicio([EVENTO])

        actualizado = servicio.modificar_evento(
            1, {"nombre_evento": "Jazz en vivo"}
        )

        assert actualizado["nombre_evento"] == "Jazz en vivo"
        assert actualizado["nombre_artista"] == "Trío Azul"
        assert actualizado["costo_artista"] == 250000
        assert servicio.repo.updates == [
            (1, {"nombre_evento": "Jazz en vivo"})
        ]

    def test_activar_y_desactivar_evento(self):
        servicio = _servicio([EVENTO, EVENTO_INACTIVO])

        activado = servicio.activar_evento(2)
        desactivado = servicio.desactivar_evento(1)

        assert activado["activo"] is True
        assert desactivado["activo"] is False
        assert servicio.repo.updates == [
            (2, {"activo": True}),
            (1, {"activo": False}),
        ]

    def test_evento_inexistente(self):
        servicio = _servicio()

        with pytest.raises(NotFoundError):
            servicio.modificar_evento(99, {"nombre_evento": "Otro"})

    def test_identificador_invalido(self):
        servicio = _servicio()

        with pytest.raises(ValidationError):
            servicio.consultar_evento("abc")

    def test_fechas_actividad_se_delegan_al_repositorio(self):
        servicio = _servicio()

        assert servicio.fechas_actividad() == {
            1: {"primera": "2026-01-10", "ultima": "2026-01-12"}
        }


class FakeQuery:
    def __init__(self, filas, error=None):
        self.filas = filas
        self.error = error
        self.rangos = []
        self._inicio = 0
        self._fin = 0

    def select(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def range(self, inicio, fin):
        self.rangos.append((inicio, fin))
        self._inicio = inicio
        self._fin = fin
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.filas[self._inicio:self._fin + 1])


class FakeClient:
    def __init__(self, por_tabla):
        self.por_tabla = por_tabla
        self.consultas = []

    def table(self, nombre):
        self.consultas.append(nombre)
        return FakeQuery(self.por_tabla.get(nombre, []))


def _repo_eventos(por_tabla):
    repo = object.__new__(EventosRepository)
    repo.table_name = "dim_evento"
    repo.client = FakeClient(por_tabla)
    return repo


class TestRepositorioEventos:
    def test_fechas_actividad_combina_ventas_y_movimientos(self):
        repo = _repo_eventos(
            {
                "hecho_venta_fudo": [
                    {"id_evento": 1, "fecha_venta": "2026-01-10"},
                    {"id_evento": 1, "fecha_venta": "2026-01-12"},
                    {"id_evento": None, "fecha_venta": "2026-01-30"},
                    {"id_evento": 2, "fecha_venta": None},
                ],
                "hecho_inventario": [
                    {
                        "id_evento": 1,
                        "fecha_hora_registro": "2026-01-11T20:00:00",
                    },
                    {
                        "id_evento": 2,
                        "fecha_hora_registro": "2026-02-01T10:30:00",
                    },
                ],
            }
        )

        actividad = repo.fechas_actividad()

        assert actividad[1] == {"primera": "2026-01-10", "ultima": "2026-01-12"}
        assert actividad[2] == {"primera": "2026-02-01", "ultima": "2026-02-01"}
        assert repo.client.consultas == ["hecho_venta_fudo", "hecho_inventario"]


class TestDataEventos:
    def test_listar_admin_exige_permisos(self, monkeypatch):
        servicio = FakeEventosService([EVENTO])
        monkeypatch.setattr("data.eventos.EventosService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            listar_eventos_admin(usuario=OPERARIO)

        assert servicio.solo_activos is None

    def test_listar_admin_incluye_inactivos(self, monkeypatch):
        servicio = FakeEventosService([EVENTO, EVENTO_INACTIVO])
        monkeypatch.setattr("data.eventos.EventosService", lambda: servicio)

        filas = listar_eventos_admin(usuario=ADMIN)

        assert len(filas) == 2
        assert servicio.solo_activos is False

    def test_registrar_invalida_cache(self, monkeypatch):
        servicio = FakeEventosService()
        monkeypatch.setattr("data.eventos.EventosService", lambda: servicio)
        limpiezas = []
        monkeypatch.setattr(
            "data.eventos.limpiar_cache", lambda: limpiezas.append(True)
        )

        registrar_evento(
            {"nombre_evento": "Noche de jazz"}, usuario=ADMIN
        )

        assert len(servicio.registrados) == 1
        assert limpiezas == [True]

    def test_cambiar_estado_exige_permisos(self, monkeypatch):
        servicio = FakeEventosService()
        monkeypatch.setattr("data.eventos.EventosService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            cambiar_estado_evento(1, False, usuario=OPERARIO)

        assert servicio.estados == []

    def test_actividad_exige_permisos(self, monkeypatch):
        servicio = FakeEventosService()
        monkeypatch.setattr("data.eventos.EventosService", lambda: servicio)

        with pytest.raises(AuthorizationError):
            actividad_eventos_admin(usuario=OPERARIO)

    def test_error_de_conexion_se_traduce(self, monkeypatch):
        servicio = FakeEventosService(error=SupabaseConnectionError("sin red"))
        monkeypatch.setattr("data.eventos.EventosService", lambda: servicio)

        with pytest.raises(ErrorDatos) as info:
            listar_eventos_admin(usuario=ADMIN)

        assert info.value.tipo == CONEXION


class TestVistaEventos:
    def test_filtrar_por_texto_tipo_y_estado(self):
        eventos = [EVENTO, EVENTO_INACTIVO]

        assert [
            fila["id_evento"]
            for fila in filtrar_eventos(eventos, texto="trío")
        ] == [1]
        assert [
            fila["id_evento"]
            for fila in filtrar_eventos(eventos, tipo="Festival")
        ] == [2]
        assert [
            fila["id_evento"]
            for fila in filtrar_eventos(eventos, estado="Activos")
        ] == [1]
        assert [
            fila["id_evento"]
            for fila in filtrar_eventos(eventos, estado="Inactivos")
        ] == [2]

    def test_duplicados_detecta_solo_el_mismo_nombre(self):
        eventos = [
            EVENTO,
            {**EVENTO, "id_evento": 4, "nombre_evento": "  NOCHE DE JAZZ "},
            EVENTO_INACTIVO,
        ]

        assert [fila["id_evento"] for fila in _duplicados("Noche de jazz", eventos)] == [
            1,
            4,
        ]
        assert [
            fila["id_evento"]
            for fila in _duplicados("Noche de jazz", eventos, exclude_id=1)
        ] == [4]
        assert _duplicados("Otro evento", eventos) == []

    def test_agrupar_artistas_construye_vista_derivada(self):
        grupos = agrupar_artistas([EVENTO, EVENTO, EVENTO_INACTIVO, EVENTO_SIN_ARTISTA])
        por_nombre = {grupo["artista"]: grupo for grupo in grupos}

        assert por_nombre["Trío Azul"]["eventos"] == 2
        assert por_nombre["Trío Azul"]["activos"] == 2
        assert por_nombre["Trío Azul"]["costo_total"] == 500000
        assert por_nombre["Banda Sur"]["activos"] == 0
        assert por_nombre["Sin artista"]["eventos"] == 1
        assert grupos[-1]["artista"] == "Sin artista"

    def test_rango_actividad(self):
        actividad = {
            1: {"primera": "2026-01-10", "ultima": "2026-01-12"},
            2: {"primera": "2026-01-10", "ultima": "2026-01-10"},
        }

        assert _rango_actividad(actividad, 1) == "10/01/2026 – 12/01/2026"
        assert _rango_actividad(actividad, 2) == "10/01/2026"
        assert _rango_actividad(actividad, 3) == "Sin actividad vinculada"

    def test_tabla_muestra_evento_artista_y_actividad(self):
        html = _tabla_eventos(
            [EVENTO, EVENTO_INACTIVO],
            {1: {"primera": "2026-01-10", "ultima": "2026-01-12"}},
        )

        assert "Noche de jazz" in html
        assert "Trío Azul" in html
        assert "Festival de verano" in html
        assert "10/01/2026 – 12/01/2026" in html
        assert "Sin actividad vinculada" in html
        assert "Inactivo" in html

    def test_metricas_no_pasa_argumentos_no_soportados(self, monkeypatch):
        llamadas = []

        def falso_metric_grid(items, **kwargs):
            llamadas.append((list(items), kwargs))

        monkeypatch.setattr(vista_eventos, "metric_grid", falso_metric_grid)

        _metricas([EVENTO, EVENTO_INACTIVO, EVENTO_SIN_ARTISTA])

        assert len(llamadas) == 1
        items, kwargs = llamadas[0]
        assert len(items) == 4
        assert kwargs == {}


def _app_eventos(monkeypatch, filas, usuario, actividad=None):
    monkeypatch.setattr(
        vista_eventos,
        "listar_eventos_admin",
        lambda usuario=None: filas,
    )
    monkeypatch.setattr(
        vista_eventos,
        "actividad_eventos_admin",
        lambda usuario=None: actividad or {},
    )
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=30,
    )
    app.session_state["logged_in"] = True
    app.session_state["user"] = usuario
    app.session_state["page"] = "eventos"
    app.run()
    return app


class TestInterfazEventos:
    def test_admin_ve_eventos_artistas_y_formulario(self, monkeypatch):
        app = _app_eventos(
            monkeypatch,
            [EVENTO, EVENTO_INACTIVO, EVENTO_SIN_ARTISTA],
            ADMIN,
            actividad={1: {"primera": "2026-01-10", "ultima": "2026-01-12"}},
        )

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Noche de jazz" in contenido
        assert "Festival de verano" in contenido
        assert "Trío Azul" in contenido
        assert "Artistas" in contenido
        assert "10/01/2026 – 12/01/2026" in contenido
        assert "ink-metrics--4" in contenido
        assert "Registrar evento" in contenido
        assert any(
            campo.label == "Nombre del evento" for campo in app.text_input
        )

    def test_catalogo_vacio_permite_crear_el_primero(self, monkeypatch):
        app = _app_eventos(monkeypatch, [], ADMIN)

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Aún no hay eventos registrados" in contenido
        assert "Aún no hay artistas para mostrar" in contenido
        assert any(
            campo.label == "Nombre del evento" for campo in app.text_input
        )

    def test_operario_no_accede_a_eventos(self, monkeypatch):
        def prohibido(usuario=None):
            raise AssertionError("La capa de datos no debe consultarse")

        monkeypatch.setattr(vista_eventos, "listar_eventos_admin", prohibido)
        app = _app_eventos(monkeypatch, [], OPERARIO)

        assert not app.exception
        assert any("permisos" in str(error.value) for error in app.error)
