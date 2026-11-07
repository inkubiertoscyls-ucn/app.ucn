"""Pruebas de la Etapa 6: administración de usuarios.

Se usan repositorios y servicios dobles. Ninguna prueba escribe en Supabase.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from core.auth_password import hash_password
from core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    SupabaseConnectionError,
)
from core.utils import normalizar_rut
from data.errors import CONEXION, ErrorDatos
from data.usuarios import activar_usuario, desactivar_usuario
from services.usuarios import UsuariosService
from views import usuarios as vista_usuarios
from views.usuarios import _metricas, _tabla_usuarios, filtrar_usuarios

ADMIN = {
    "rut_usuario": "12345678-9",
    "nombre_usuario": "Ana Admin",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
    "fecha_creacion": "2026-01-02T10:30:00+00:00",
}
OTRO_ADMIN = {
    "rut_usuario": "22222222-2",
    "nombre_usuario": "Bruno Admin",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
    "fecha_creacion": "2026-01-03T10:30:00+00:00",
}
OPERARIO = {
    "rut_usuario": "11111111-1",
    "nombre_usuario": "Beto Operario",
    "rol": "Operario",
    "area_asignada": "Barra",
    "activo": False,
    "fecha_creacion": "2026-02-04T10:30:00+00:00",
}
OPERARIO_ACTIVO = {
    "rut_usuario": "33333333-3",
    "nombre_usuario": "Carla Muñoz",
    "rol": "Operario",
    "area_asignada": "Cocina",
    "activo": True,
    "fecha_creacion": "2026-02-05T10:30:00+00:00",
}


class FakeRepo:
    """Repositorio en memoria para probar las reglas del servicio."""

    def __init__(self, usuarios=None):
        self.usuarios = {
            normalizar_rut(fila["rut_usuario"]): dict(fila)
            for fila in usuarios or []
        }
        self.updates = []
        self.deactivations = []
        self.creados = []

    def get_by_rut(self, rut):
        fila = self.usuarios.get(normalizar_rut(rut))
        return dict(fila) if fila else None

    def get_by_rol(self, rol):
        return [
            dict(fila)
            for fila in self.usuarios.values()
            if fila.get("rol") == rol
        ]

    def update(self, id_column, id_value, data):
        self.updates.append((id_column, id_value, dict(data)))
        fila = self.usuarios.get(id_value)
        if fila is not None:
            fila.update(data)
            return dict(fila)
        return dict(data)

    def deactivate(self, id_column, id_value):
        self.deactivations.append((id_column, id_value))
        return self.update(id_column, id_value, {"activo": False})

    def create(self, data):
        self.creados.append(dict(data))
        self.usuarios[data["rut_usuario"]] = dict(data)
        return dict(data)


def _servicio(usuarios=None):
    servicio = UsuariosService()
    servicio.repo = FakeRepo(usuarios)
    return servicio


class TestRegistroSeguro:
    def test_operario_siempre_nace_inactivo(self):
        servicio = _servicio()
        resultado = servicio.registrar_usuario(
            {
                "rut_usuario": "11111111-1",
                "nombre_usuario": "Operario Nuevo",
                "rol": "Operario",
                "area_asignada": "Barra",
                "activo": True,
                "password": "TestPass123",
            }
        )

        assert resultado["rol"] == "Operario"
        assert resultado["activo"] is False
        assert "password" not in resultado
        assert resultado["password_hash"].startswith("$argon2")

    def test_publico_no_puede_crear_administrador(self):
        servicio = _servicio()
        with pytest.raises(AuthorizationError):
            servicio.registrar_usuario(
                {
                    "rut_usuario": "11111111-1",
                    "nombre_usuario": "Intruso",
                    "rol": "Administrador",
                    "password": "TestPass123",
                }
            )

    def test_administrador_autorizado_puede_crear_administrador(self):
        servicio = _servicio([ADMIN])
        resultado = servicio.registrar_usuario(
            {
                "rut_usuario": "22222222-2",
                "nombre_usuario": "Nueva Admin",
                "rol": "Administrador",
                "password": "TestPass123",
            },
            creado_por_rut=ADMIN["rut_usuario"],
        )

        assert resultado["rol"] == "Administrador"
        assert resultado["activo"] is True

    def test_operario_inactivo_no_inicia_sesion(self):
        servicio = _servicio(
            [
                {
                    **OPERARIO,
                    "password_hash": hash_password("TestPass123"),
                }
            ]
        )

        with pytest.raises(AuthenticationError):
            servicio.autenticar(OPERARIO["rut_usuario"], "TestPass123")


class TestActivacionYDesactivacion:
    def test_activar_operario(self):
        servicio = _servicio([ADMIN, OPERARIO])

        resultado = servicio.activar_usuario(
            OPERARIO["rut_usuario"],
            autorizado_por=ADMIN["rut_usuario"],
        )

        assert resultado["activo"] is True
        assert servicio.repo.updates == [
            (
                "rut_usuario",
                normalizar_rut(OPERARIO["rut_usuario"]),
                {"activo": True},
            )
        ]

    def test_desactivar_operario_conserva_historial(self):
        servicio = _servicio([ADMIN, OPERARIO_ACTIVO])

        resultado = servicio.desactivar_usuario(
            OPERARIO_ACTIVO["rut_usuario"],
            autorizado_por=ADMIN["rut_usuario"],
        )

        assert resultado["activo"] is False
        assert servicio.repo.deactivations == [
            ("rut_usuario", normalizar_rut(OPERARIO_ACTIVO["rut_usuario"]))
        ]
        # El usuario sigue existiendo: no se borra la fila.
        assert normalizar_rut(OPERARIO_ACTIVO["rut_usuario"]) in servicio.repo.usuarios

    def test_operario_no_puede_activar(self):
        servicio = _servicio([OPERARIO_ACTIVO, OPERARIO])

        with pytest.raises(AuthorizationError):
            servicio.activar_usuario(
                OPERARIO["rut_usuario"],
                autorizado_por=OPERARIO_ACTIVO["rut_usuario"],
            )

        assert servicio.repo.updates == []

    def test_operario_no_puede_desactivar(self):
        servicio = _servicio([OPERARIO_ACTIVO, ADMIN])

        with pytest.raises(AuthorizationError):
            servicio.desactivar_usuario(
                ADMIN["rut_usuario"],
                autorizado_por=OPERARIO_ACTIVO["rut_usuario"],
            )

        assert servicio.repo.deactivations == []

    def test_no_puede_desactivarse_a_si_mismo(self):
        servicio = _servicio([ADMIN, OTRO_ADMIN])

        with pytest.raises(AuthorizationError):
            servicio.desactivar_usuario(
                ADMIN["rut_usuario"],
                autorizado_por=ADMIN["rut_usuario"],
            )

        assert servicio.repo.deactivations == []

    def test_no_puede_dejar_sin_administradores(self):
        servicio = _servicio([ADMIN])

        with pytest.raises(AuthorizationError):
            servicio.desactivar_usuario(ADMIN["rut_usuario"])

        assert servicio.repo.deactivations == []

    def test_puede_desactivar_admin_si_queda_otro_activo(self):
        servicio = _servicio([ADMIN, OTRO_ADMIN])

        resultado = servicio.desactivar_usuario(
            OTRO_ADMIN["rut_usuario"],
            autorizado_por=ADMIN["rut_usuario"],
        )

        assert resultado["activo"] is False
        assert servicio.repo.deactivations == [
            ("rut_usuario", normalizar_rut(OTRO_ADMIN["rut_usuario"]))
        ]

    def test_desactivar_usuario_inexistente(self):
        servicio = _servicio([ADMIN])
        with pytest.raises(NotFoundError):
            servicio.desactivar_usuario(
                "44444444-4",
                autorizado_por=ADMIN["rut_usuario"],
            )

    def test_activar_usuario_inexistente(self):
        servicio = _servicio([ADMIN])
        with pytest.raises(NotFoundError):
            servicio.activar_usuario(
                "44444444-4",
                autorizado_por=ADMIN["rut_usuario"],
            )


class FakeServicioDatos:
    def __init__(self, resultado=None, error=None):
        self.resultado = resultado or {}
        self.error = error
        self.llamadas = []

    def activar_usuario(self, rut, autorizado_por=None):
        self.llamadas.append(("activar", rut, autorizado_por))
        if self.error:
            raise self.error
        return dict(self.resultado)

    def desactivar_usuario(self, rut, autorizado_por=None):
        self.llamadas.append(("desactivar", rut, autorizado_por))
        if self.error:
            raise self.error
        return dict(self.resultado)


class TestCapaDeDatos:
    def test_operario_no_puede_activar(self, monkeypatch):
        fake = FakeServicioDatos(resultado={"activo": True})
        monkeypatch.setattr("data.usuarios.UsuariosService", lambda: fake)

        with pytest.raises(AuthorizationError):
            activar_usuario(OPERARIO["rut_usuario"], usuario=OPERARIO_ACTIVO)

        assert fake.llamadas == []

    def test_operario_no_puede_desactivar(self, monkeypatch):
        fake = FakeServicioDatos(resultado={"activo": False})
        monkeypatch.setattr("data.usuarios.UsuariosService", lambda: fake)

        with pytest.raises(AuthorizationError):
            desactivar_usuario(ADMIN["rut_usuario"], usuario=OPERARIO_ACTIVO)

        assert fake.llamadas == []

    def test_admin_activa_y_no_expone_hash(self, monkeypatch):
        fake = FakeServicioDatos(
            resultado={
                "rut_usuario": OPERARIO["rut_usuario"],
                "nombre_usuario": OPERARIO["nombre_usuario"],
                "activo": True,
                "password_hash": "$argon2id$secreto",
            }
        )
        monkeypatch.setattr("data.usuarios.UsuariosService", lambda: fake)

        resultado = activar_usuario(OPERARIO["rut_usuario"], usuario=ADMIN)

        assert resultado["activo"] is True
        assert "password_hash" not in resultado
        assert fake.llamadas == [
            ("activar", OPERARIO["rut_usuario"], ADMIN["rut_usuario"])
        ]

    def test_admin_desactiva_pasando_autorizador(self, monkeypatch):
        fake = FakeServicioDatos(resultado={"activo": False})
        monkeypatch.setattr("data.usuarios.UsuariosService", lambda: fake)

        resultado = desactivar_usuario(OPERARIO["rut_usuario"], usuario=ADMIN)

        assert resultado == {"activo": False}
        assert fake.llamadas == [
            ("desactivar", OPERARIO["rut_usuario"], ADMIN["rut_usuario"])
        ]

    def test_error_de_conexion_se_traduce(self, monkeypatch):
        fake = FakeServicioDatos(error=SupabaseConnectionError("sin red"))
        monkeypatch.setattr("data.usuarios.UsuariosService", lambda: fake)

        with pytest.raises(ErrorDatos) as info:
            activar_usuario(OPERARIO["rut_usuario"], usuario=ADMIN)

        assert info.value.tipo == CONEXION


class TestFiltrosYTabla:
    FILAS = [ADMIN, OPERARIO, OPERARIO_ACTIVO]

    def test_busca_por_nombre_sin_acentos(self):
        resultado = filtrar_usuarios(self.FILAS, texto="munoz")
        assert [fila["rut_usuario"] for fila in resultado] == [
            OPERARIO_ACTIVO["rut_usuario"]
        ]

    def test_busca_por_rut_sin_puntos_ni_guiones(self):
        resultado = filtrar_usuarios(self.FILAS, texto="11111111")
        assert [fila["rut_usuario"] for fila in resultado] == [
            OPERARIO["rut_usuario"]
        ]

    def test_filtra_por_rol_estado_y_area(self):
        resultado = filtrar_usuarios(
            self.FILAS,
            rol="Operario",
            estado="Activos",
            area="Cocina",
        )
        assert [fila["rut_usuario"] for fila in resultado] == [
            OPERARIO_ACTIVO["rut_usuario"]
        ]

    def test_filtro_vacio_devuelve_todas_ordenadas(self):
        resultado = filtrar_usuarios(self.FILAS)
        assert len(resultado) == 3
        assert resultado[0]["activo"] is True

    def test_area_global_no_filtra_y_area_todas_filtra_admin(self):
        assert len(filtrar_usuarios(self.FILAS, area="Todas las áreas")) == 3
        resultado = filtrar_usuarios(self.FILAS, area="Todas")
        assert [fila["rut_usuario"] for fila in resultado] == [
            ADMIN["rut_usuario"]
        ]

    def test_filtro_sin_coincidencias(self):
        assert filtrar_usuarios(self.FILAS, texto="no existe") == []

    def test_tabla_muestra_estados_y_no_expone_password(self):
        filas = [
            {**ADMIN, "password_hash": "$argon2id$secreto"},
            {**OPERARIO, "password_hash": "$argon2id$secreto"},
        ]

        html = _tabla_usuarios(filas, actual_rut=ADMIN["rut_usuario"])

        assert "Ana Admin" in html
        assert "Beto Operario" in html
        assert "Activo" in html
        assert "Inactivo" in html
        assert "(tú)" in html
        assert "password_hash" not in html
        assert "$argon2" not in html


def _app_usuarios(monkeypatch, filas, usuario):
    monkeypatch.setattr(vista_usuarios, "listar_usuarios", lambda usuario=None: filas)
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=30,
    )
    app.session_state["logged_in"] = True
    app.session_state["user"] = usuario
    app.session_state["page"] = "usuarios"
    app.run()
    return app


class TestInterfaz:
    def test_metricas_no_pasa_argumentos_no_soportados(self, monkeypatch):
        llamadas = []

        def falso_metric_grid(items, **kwargs):
            llamadas.append((list(items), kwargs))

        monkeypatch.setattr(vista_usuarios, "metric_grid", falso_metric_grid)

        _metricas([ADMIN, OTRO_ADMIN, OPERARIO, OPERARIO_ACTIVO])

        assert len(llamadas) == 1
        items, kwargs = llamadas[0]
        assert len(items) == 4
        assert kwargs == {}

    def test_admin_ve_listado_sin_excepciones(self, monkeypatch):
        app = _app_usuarios(monkeypatch, [ADMIN, OPERARIO], ADMIN)

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Ana Admin" in contenido
        assert "Beto Operario" in contenido
        assert "Inactivo" in contenido
        assert "password_hash" not in contenido

    def test_metricas_de_usuarios_renderizan_grilla_de_cuatro_columnas(
        self, monkeypatch
    ):
        app = _app_usuarios(
            monkeypatch,
            [ADMIN, OTRO_ADMIN, OPERARIO, OPERARIO_ACTIVO],
            ADMIN,
        )

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "ink-metrics--4" in contenido
        assert "Administradores" in contenido

    def test_error_de_renderizado_no_se_muestra_como_conexion(self, monkeypatch):
        def metric_grid_roto(*args, **kwargs):
            raise TypeError(
                "metric_grid() got an unexpected keyword argument 'columns'"
            )

        monkeypatch.setattr(vista_usuarios, "metric_grid", metric_grid_roto)
        app = _app_usuarios(monkeypatch, [ADMIN, OPERARIO], ADMIN)

        assert app.exception
        texto = "\n".join(str(item.value) for item in app.exception)
        assert "unexpected keyword argument 'columns'" in texto
        assert not any(
            "conectar" in str(error.value).lower() for error in app.error
        )

    def test_operario_no_accede_a_usuarios(self, monkeypatch):
        def prohibido(usuario=None):
            raise AssertionError("La capa de datos no debe consultarse")

        monkeypatch.setattr(vista_usuarios, "listar_usuarios", prohibido)
        app = _app_usuarios(monkeypatch, [], OPERARIO_ACTIVO)

        assert not app.exception
        assert any("permisos" in str(error.value) for error in app.error)

    def test_estado_vacio_se_muestra(self, monkeypatch):
        app = _app_usuarios(monkeypatch, [], ADMIN)

        assert not app.exception
        contenido = "\n".join(str(item.value) for item in app.markdown)
        assert "Aún no hay usuarios registrados" in contenido

    def test_admin_puede_activar_desde_la_interfaz(self, monkeypatch):
        llamadas = []

        def falso_activar(rut, *, usuario=None):
            llamadas.append((rut, usuario.get("rut_usuario")))
            return {"rut_usuario": rut, "activo": True}

        monkeypatch.setattr(vista_usuarios, "activar_usuario", falso_activar)
        app = _app_usuarios(monkeypatch, [OPERARIO], ADMIN)

        app.checkbox(
            key=f"usr_confirmar_activar_{OPERARIO['rut_usuario']}"
        ).check().run()
        app.button(key="usr_activar").click().run()

        assert llamadas == [
            (OPERARIO["rut_usuario"], ADMIN["rut_usuario"])
        ]

    def test_no_ofrece_desactivar_la_propia_cuenta(self, monkeypatch):
        app = _app_usuarios(monkeypatch, [ADMIN, OPERARIO_ACTIVO], ADMIN)

        assert not app.exception
        assert any(
            "No puedes desactivar tu propia cuenta" in str(info.value)
            for info in app.info
        )
        assert not any(
            boton.label == "Desactivar cuenta" for boton in app.button
        )
