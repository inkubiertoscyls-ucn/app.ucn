"""Pruebas de la Etapa 5: importación FUDO con archivos controlados.

No se escribe en Supabase: el cliente y el repositorio de ventas se sustituyen
por dobles de prueba y los archivos se generan en directorios temporales.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.fudo import (
    archivo_temporal,
    importar_ventas,
    inspeccionar_archivo,
    previsualizar_importacion,
)
from services.fudo_import import FudoImportService, _hash_canonico

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

MAPEO = {
    "Fecha": "fecha_venta",
    "Total": "total_venta",
    "Cantidad": "cantidad_total",
    "Producto": "producto_identificado",
}

CSV_VALIDO = (
    "Fecha,Total,Cantidad,Producto\n"
    "10-01-2026,5.000,2,Pisco Sour\n"
    "fecha-invalida,3000,1,Producto malo\n"
    "10-01-2026,5.000,2,Pisco Sour\n"
    "11-01-2026,2500,1,Cerveza\n"
).encode("utf-8")


class FakeVentasRepo:
    def __init__(self):
        self.registros = []
        self.hashes = set()
        self.llamadas = []

    def hashes_existentes(self):
        return set(self.hashes)

    def create(self, datos):
        self.registros.append(dict(datos))
        if datos.get("hash_registro"):
            self.hashes.add(str(datos["hash_registro"]))
        return datos

    def listar(self, **kwargs):
        self.llamadas.append(("listar", kwargs))
        return [{"id_venta_fudo": 1, "total_venta": 1000}]

    def listar_recientes(self, limite=50):
        self.llamadas.append(("listar_recientes", limite))
        return []

    def hashes(self):
        return set(self.hashes)


@pytest.fixture
def servicio(monkeypatch):
    monkeypatch.setattr(
        "services.fudo_import.get_supabase_client", lambda: MagicMock()
    )
    return FudoImportService()


def _df():
    return pd.DataFrame(
        [
            {
                "Fecha": "10-01-2026",
                "Total": "5.000",
                "Cantidad": "2",
                "Producto": "Pisco Sour",
            },
            {
                "Fecha": "fecha-invalida",
                "Total": "3000",
                "Cantidad": "1",
                "Producto": "Producto malo",
            },
            {
                "Fecha": "10-01-2026",
                "Total": "5000",
                "Cantidad": "2",
                "Producto": "Pisco Sour",
            },
            {
                "Fecha": "11-01-2026",
                "Total": "2500",
                "Cantidad": "",
                "Producto": "Cerveza",
            },
            {
                "Fecha": None,
                "Total": None,
                "Cantidad": None,
                "Producto": None,
            },
        ]
    )


def test_analisis_clasifica_validos_errores_duplicados_y_vacios(servicio):
    resultado = servicio.analizar_dataframe(_df(), MAPEO)

    assert resultado["total_filas"] == 5
    assert resultado["filas_vacias"] == 1
    assert resultado["validos"] == 2
    assert resultado["con_error"] == 1
    assert resultado["duplicados"] == 1
    assert resultado["importables"] == 2
    assert resultado["advertencias"] == 1
    assert any("fecha" in error["detalle"].lower() for error in resultado["errores"])
    assert any(
        "mismos datos" in error["detalle"].lower()
        or "repite" in error["detalle"].lower()
        for error in resultado["errores"]
    )


def test_monto_chileno_y_total_con_separadores(servicio):
    df = pd.DataFrame(
        [
            {
                "Fecha": "10-01-2026",
                "Total": "1.500",
                "Cantidad": "",
                "Producto": "A",
            },
            {
                "Fecha": "10-01-2026",
                "Total": "$12.345,50",
                "Cantidad": "",
                "Producto": "B",
            },
        ]
    )
    resultado = servicio.analizar_dataframe(df, MAPEO)
    totales = [fila["total"] for fila in resultado["filas"]]
    assert totales == [1500.0, 12345.5]


def test_mapeo_requiere_campos_obligatorios(servicio):
    with pytest.raises(Exception) as error:
        servicio.normalizar_mapeo({"Fecha": "fecha_venta"})
    assert "obligatoria" in str(error.value)


def test_hashes_son_deterministas_y_detectan_duplicados(servicio):
    df = pd.DataFrame(
        [
            {
                "Fecha": "10-01-2026",
                "Total": "1000",
                "Cantidad": "1",
                "Producto": "A",
            },
            {
                "Fecha": "10-01-2026",
                "Total": "1000",
                "Cantidad": "1",
                "Producto": "A",
            },
        ]
    )
    resultado = servicio.analizar_dataframe(df, MAPEO)
    assert resultado["duplicados"] == 1

    hash_uno = _hash_canonico("2026-01-10", 1000.0, 1.0, "A")
    assert hash_uno == _hash_canonico("2026-01-10", 1000.0, 1.0, " a ")
    assert len(hash_uno) == 64


def test_lectura_real_de_csv_y_excel(tmp_path, servicio):
    csv_path = tmp_path / "ventas.csv"
    csv_path.write_bytes(CSV_VALIDO)
    hojas = servicio.hojas(str(csv_path))
    assert hojas == ["csv"]
    df = servicio.leer_hoja(str(csv_path))
    assert list(df.columns) == ["Fecha", "Total", "Cantidad", "Producto"]

    excel_path = tmp_path / "ventas.xlsx"
    pd.DataFrame(
        [{"Fecha": "2026-01-10", "Total": 1000, "Producto": "A"}]
    ).to_excel(excel_path, index=False, sheet_name="Ventas")
    assert "Ventas" in servicio.hojas(str(excel_path))
    df_excel = servicio.leer_hoja(str(excel_path), "Ventas")
    assert list(df_excel.columns) == ["Fecha", "Total", "Producto"]


def test_inspeccion_real_de_archivo_excel(tmp_path, servicio):
    excel_path = tmp_path / "ventas.xlsx"
    pd.DataFrame(
        [{"Fecha": "2026-01-10", "Total": 1000, "Producto": "A"}]
    ).to_excel(excel_path, index=False, sheet_name="Hoja 1")
    datos = servicio.inspeccionar_archivo(str(excel_path))
    assert datos["tipo"] == "excel"
    assert "Hoja 1" in datos["hojas"]
    assert "Fecha" in datos["columnas_por_hoja"]["Hoja 1"]


def test_archivo_temporal_limpia_al_salir():
    ruta_final = None
    with archivo_temporal(CSV_VALIDO, "ventas.csv") as (ruta, nombre):
        ruta_final = ruta
        assert nombre == "ventas.csv"
        assert __import__("pathlib").Path(ruta).exists()
    assert not __import__("pathlib").Path(ruta_final).exists()


def test_archivo_temporal_recorta_nombre_largo_conservando_extension():
    nombre_largo = "v" * 300 + ".csv"
    with archivo_temporal(CSV_VALIDO, nombre_largo) as (ruta, nombre):
        assert nombre.endswith(".csv")
        assert len(nombre) <= 255
        assert __import__("pathlib").Path(ruta).suffix == ".csv"


def test_archivo_temporal_rechaza_extension_vacia_y_tamano(monkeypatch):
    with pytest.raises(ErrorDatos):
        with archivo_temporal(b"datos", "ventas.txt"):
            pass

    with pytest.raises(ErrorDatos):
        with archivo_temporal(b"", "ventas.csv"):
            pass

    monkeypatch.setattr("data.fudo.TAMANO_MAXIMO_BYTES", 5)
    with pytest.raises(ErrorDatos):
        with archivo_temporal(b"123456", "ventas.csv"):
            pass


def test_previsualizacion_e_importacion_confirmada_sin_escribir_en_supabase(
    monkeypatch, servicio
):
    repo = FakeVentasRepo()
    servicio.ventas_repo = repo
    monkeypatch.setattr("data.fudo.FudoImportService", lambda: servicio)
    monkeypatch.setattr("data.fudo.VentasFudoRepository", lambda: repo)

    previa = previsualizar_importacion(
        CSV_VALIDO,
        "ventas.csv",
        hoja="csv",
        mapeo=MAPEO,
        usuario=ADMIN,
    )
    assert previa["importables"] == 2
    assert repo.registros == []

    with pytest.raises(ErrorDatos):
        importar_ventas(
            CSV_VALIDO,
            "ventas.csv",
            hoja="csv",
            mapeo=MAPEO,
            confirmado=False,
            usuario=ADMIN,
        )
    assert repo.registros == []

    resultado = importar_ventas(
        CSV_VALIDO,
        "ventas.csv",
        hoja="csv",
        mapeo=MAPEO,
        confirmado=True,
        usuario=ADMIN,
    )

    assert resultado["importados"] == 2
    assert resultado["rechazados"] == 1
    assert resultado["duplicados"] == 1
    assert len(repo.registros) == 2
    for registro in repo.registros:
        assert registro["id_producto_relacionado"] is None
        assert registro["id_evento"] is None
        assert registro["importado_por"] == ADMIN["rut_usuario"]
        assert registro["origen_archivo"] == "ventas.csv"
        assert isinstance(registro["datos_raw"], dict)
        assert len(registro["hash_registro"]) == 64


def test_importacion_detecta_duplicados_ya_guardados(monkeypatch, servicio):
    repo = FakeVentasRepo()
    servicio.ventas_repo = repo
    monkeypatch.setattr("data.fudo.FudoImportService", lambda: servicio)
    monkeypatch.setattr("data.fudo.VentasFudoRepository", lambda: repo)

    primero = importar_ventas(
        CSV_VALIDO,
        "ventas.csv",
        hoja="csv",
        mapeo=MAPEO,
        confirmado=True,
        usuario=ADMIN,
    )
    assert primero["importados"] == 2

    segundo = importar_ventas(
        CSV_VALIDO,
        "ventas.csv",
        hoja="csv",
        mapeo=MAPEO,
        confirmado=True,
        usuario=ADMIN,
    )
    assert segundo["importados"] == 0
    assert segundo["duplicados"] == 3
    assert len(repo.registros) == 2


def test_importacion_sin_cantidad_advierte_y_no_costea(monkeypatch, servicio):
    repo = FakeVentasRepo()
    servicio.ventas_repo = repo
    monkeypatch.setattr("data.fudo.FudoImportService", lambda: servicio)
    monkeypatch.setattr("data.fudo.VentasFudoRepository", lambda: repo)

    contenido = (
        "Fecha,Total,Producto\n"
        "10-01-2026,5000,Pisco Sour\n"
    ).encode("utf-8")
    mapeo = {
        "Fecha": "fecha_venta",
        "Total": "total_venta",
        "Producto": "producto_identificado",
    }
    resultado = importar_ventas(
        contenido,
        "sin_cantidad.csv",
        hoja="csv",
        mapeo=mapeo,
        confirmado=True,
        usuario=ADMIN,
    )
    assert resultado["importados"] == 1
    assert resultado["advertencias_generales"]
    assert repo.registros[0]["cantidad_total"] is None


def test_permisos_de_operario_en_capa_de_datos():
    with pytest.raises(AuthorizationError):
        inspeccionar_archivo(CSV_VALIDO, "ventas.csv", usuario=OPERARIO)

    with pytest.raises(AuthorizationError):
        previsualizar_importacion(
            CSV_VALIDO,
            "ventas.csv",
            hoja="csv",
            mapeo=MAPEO,
            usuario=OPERARIO,
        )

    with pytest.raises(AuthorizationError):
        importar_ventas(
            CSV_VALIDO,
            "ventas.csv",
            hoja="csv",
            mapeo=MAPEO,
            confirmado=True,
            usuario=OPERARIO,
        )
