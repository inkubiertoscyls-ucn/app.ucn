"""Pruebas de la importación de movimientos de inventario desde Excel.

Se usan repositorios dobles: ninguna prueba escribe en Supabase ni modifica el
esquema. Se cubre el flujo completo de plantilla, vista previa, duplicados,
confirmación, permisos por rol/área, tipos de movimiento y fallo sin registros
parciales.
"""
from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from core.exceptions import AuthorizationError, ValidationError
from core.stock import clasificar_stock, resumir_movimientos
from data.alertas import resumen_alertas
from data.errors import ErrorDatos
from data.importacion_inventario import (
    generar_plantilla_inventario,
    importar_entradas_inventario,
    previsualizar_importacion_inventario,
)
from services.importacion_inventario import (
    COLUMNAS,
    ETIQUETAS_COLUMNA,
    HOJA_CATALOGOS,
    HOJA_ENTRADAS,
    HOJA_MOVIMIENTOS,
    HOJA_MOVIMIENTOS_APP,
    ImportacionInventarioService,
)

ADMIN = {
    "rut_usuario": "123456789",
    "nombre_usuario": "Ana Admin",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
}
OPERARIO = {
    "rut_usuario": "111111111",
    "nombre_usuario": "Operario Bodega",
    "rol": "Operario",
    "area_asignada": "Bodega",
    "activo": True,
}
OPERARIO_BARRA = {
    "rut_usuario": "222222222",
    "nombre_usuario": "Operario Barra",
    "rol": "Operario",
    "area_asignada": "Barra",
    "activo": True,
}

PRODUCTOS = [
    {
        "id_producto": 1,
        "nombre_producto": "Aceitunas verdes",
        "costo_base": 1200,
        "unidad_medida": "kg",
        "activo": True,
    },
    {
        "id_producto": 2,
        "nombre_producto": "Aceitunas negras",
        "costo_base": 1400,
        "unidad_medida": "kg",
        "activo": False,
    },
]
AREAS = [
    {"id_area": 1, "nombre_area": "Bodega", "activo": True},
    {"id_area": 2, "nombre_area": "Barra", "activo": True},
]
PROVEEDORES = [
    {
        "rut_proveedor": "109662062",
        "nombre_proveedor": "Ana",
        "activo": True,
    }
]
TIPOS = [
    {
        "id_tipo_movimiento": 1,
        "tipo_movimiento": "Entrada",
        "factor_stock": 1,
        "activo": True,
    },
    {
        "id_tipo_movimiento": 2,
        "tipo_movimiento": "Salida",
        "factor_stock": -1,
        "activo": True,
    },
    {
        "id_tipo_movimiento": 3,
        "tipo_movimiento": "Merma",
        "factor_stock": -1,
        "activo": True,
    },
    {
        "id_tipo_movimiento": 4,
        "tipo_movimiento": "Ajuste positivo",
        "factor_stock": 1,
        "activo": True,
    },
    {
        "id_tipo_movimiento": 5,
        "tipo_movimiento": "Ajuste negativo",
        "factor_stock": -1,
        "activo": True,
    },
    {
        "id_tipo_movimiento": 6,
        "tipo_movimiento": "Tipo inactivo",
        "factor_stock": 1,
        "activo": False,
    },
]
FECHAS = {"2026-11-03": 100, "2026-11-04": 101}
USUARIOS = {
    "123456789": {**ADMIN, "activo": True},
    "111111111": {**OPERARIO, "activo": True},
    "222222222": {**OPERARIO_BARRA, "activo": True},
}


class FakeCatalogo:
    def __init__(self, filas):
        self.filas = filas

    def get_all(self, filtros=None):
        if filtros:
            return [
                fila
                for fila in self.filas
                if all(fila.get(campo) == valor for campo, valor in filtros.items())
            ]
        return list(self.filas)


class FakeFechas:
    def __init__(self, mapa=None):
        self.mapa = dict(mapa or {})

    def ids_por_fechas(self, fechas):
        return {
            str(fecha)[:10]: self.mapa[str(fecha)[:10]]
            for fecha in fechas
            if str(fecha)[:10] in self.mapa
        }


class FakeMovimientos:
    def __init__(self, existentes=None, error=None, stock=None):
        self.existentes = list(existentes or [])
        self.error = error
        self.stock = stock
        self.patron = None
        self.payloads = None
        self.llamadas = 0
        self.stock_llamadas = 0

    def observaciones_con_marcador(self, patron):
        self.patron = patron
        return list(self.existentes)

    def stock_agregado(self):
        self.stock_llamadas += 1
        if self.stock is None:
            raise RuntimeError("sin snapshot de stock")
        return list(self.stock)

    def create_many(self, filas):
        self.llamadas += 1
        if self.error:
            raise self.error
        self.payloads = [dict(fila) for fila in filas]
        return [
            {"id_hecho_inventario": indice + 1, **fila}
            for indice, fila in enumerate(self.payloads)
        ]


class FakeUsuarios:
    def __init__(self, usuarios=None):
        self.usuarios = usuarios or USUARIOS

    def get_by_rut(self, rut):
        return self.usuarios.get(str(rut))


def _servicio(movimientos=None, existentes=None, error=None, stock=None):
    movimientos = movimientos or FakeMovimientos(
        existentes=existentes, error=error, stock=stock
    )
    servicio = ImportacionInventarioService(
        productos_repo=FakeCatalogo(PRODUCTOS),
        areas_repo=FakeCatalogo(AREAS),
        proveedores_repo=FakeCatalogo(PROVEEDORES),
        tipos_repo=FakeCatalogo(TIPOS),
        fechas_repo=FakeFechas(FECHAS),
        movimientos_repo=movimientos,
        usuarios_repo=FakeUsuarios(),
    )
    return servicio, movimientos


def _archivo(filas, encabezados=None, hoja=None):
    libro = Workbook()
    hoja_libro = libro.active
    hoja_libro.title = hoja or HOJA_MOVIMIENTOS
    hoja_libro.append(
        encabezados
        if encabezados is not None
        else [ETIQUETAS_COLUMNA[columna] for columna in COLUMNAS]
    )
    for fila in filas:
        hoja_libro.append(fila)
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _archivo_dicts(filas, columnas, hoja=None):
    """Construye un Excel con las columnas indicadas y filas como diccionarios."""
    libro = Workbook()
    hoja_libro = libro.active
    hoja_libro.title = hoja or HOJA_MOVIMIENTOS
    hoja_libro.append(list(columnas))
    for fila in filas:
        hoja_libro.append([fila.get(columna) for columna in columnas])
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _fila_valida(**cambios):
    datos = {
        "fecha": "03/11/2026",
        "producto": "Aceitunas verdes",
        "area": "Bodega",
        "tipo_movimiento": "Entrada",
        "cantidad": 12,
        "costo_unitario": 1500,
        "proveedor": "Ana",
        "documento": "F-123",
        "observacion": "Compra semanal",
    }
    datos.update(cambios)
    return [datos.get(columna) for columna in COLUMNAS]


# ----------------------------------------------------------------------
# Plantilla
# ----------------------------------------------------------------------
def test_plantilla_tiene_hojas_encabezados_y_catalogos_reales():
    servicio, movimientos = _servicio()

    contenido = servicio.generar_plantilla()
    libro = load_workbook(BytesIO(contenido))

    assert {HOJA_MOVIMIENTOS, HOJA_CATALOGOS, "Instrucciones"} <= set(
        libro.sheetnames
    )
    hoja = libro[HOJA_MOVIMIENTOS]
    assert [hoja.cell(row=1, column=i + 1).value for i in range(len(COLUMNAS))] == [
        ETIQUETAS_COLUMNA[columna] for columna in COLUMNAS
    ]
    assert hoja["A2"].value is None
    assert len(hoja.data_validations.dataValidation) >= 5

    catalogo = libro[HOJA_CATALOGOS]
    assert catalogo["A2"].value == "Aceitunas verdes"
    assert catalogo["B2"].value == "Barra"
    assert catalogo["C2"].value == "Ana"
    assert movimientos.llamadas == 0


def test_hoja_entradas_es_alias_de_movimientos_para_compatibilidad():
    assert HOJA_ENTRADAS == HOJA_MOVIMIENTOS


# ----------------------------------------------------------------------
# Vista previa sin escritura
# ----------------------------------------------------------------------
def test_analisis_valido_no_escribe_nada():
    servicio, movimientos = _servicio()

    resultado = servicio.analizar(_archivo([_fila_valida()]), "movimientos.xlsx")

    assert resultado["validos"] == 1
    assert resultado["importables"] == 1
    assert resultado["con_error"] == 0
    assert resultado["duplicados"] == 0
    assert resultado["total_consideradas"] == 1
    assert resultado["filas_vacias"] == 0
    assert resultado["hoja"] == HOJA_MOVIMIENTOS
    assert "costo_unitario" in resultado["columnas"]
    assert resultado["filas"][0]["tipo"] == "Entrada"
    assert resultado["filas"][0]["responsable"] == "—"
    assert movimientos.llamadas == 0
    assert movimientos.payloads is None


def test_columnas_opcionales_faltantes_se_informan():
    servicio, _ = _servicio()
    encabezados = [
        "Fecha",
        "Producto",
        "Área",
        "Cantidad",
        "Costo unitario (CLP)",
        "Proveedor",
    ]

    resultado = servicio.analizar(
        _archivo(
            [["03/11/2026", "Aceitunas verdes", "Bodega", 12, 1500, "Ana"]],
            encabezados,
        ),
        "movimientos.xlsx",
    )

    assert resultado["validos"] == 1
    texto = " ".join(resultado["advertencias_generales"]).lower()
    assert "documento" in texto
    assert "observación" in texto
    assert "tipo de movimiento" in texto


def test_tipo_movimiento_faltante_usa_entrada_por_defecto():
    servicio, movimientos = _servicio()
    encabezados = ["Fecha", "Producto", "Área", "Cantidad", "Costo unitario (CLP)"]
    fila = ["03/11/2026", "Aceitunas verdes", "Bodega", 4, 1200]

    resultado = servicio.importar(
        _archivo([fila], encabezados), "movimientos.xlsx", "123456789", confirmado=True
    )

    assert resultado["importados"] == 1
    assert movimientos.payloads[0]["id_tipo_movimiento"] == 1


@pytest.mark.parametrize(
    "cambios,motivo",
    [
        ({"producto": "Producto inexistente"}, "no existe"),
        ({"producto": "Aceitunas negras"}, "inactivo"),
        ({"area": "Área inexistente"}, "no existe"),
        ({"cantidad": 0}, "mayor que cero"),
        ({"cantidad": -2}, "mayor que cero"),
        ({"cantidad": "abc"}, "número"),
        ({"cantidad": 1.5}, "entero"),
        ({"costo_unitario": -1}, "negativo"),
        ({"costo_unitario": "abc"}, "número"),
        ({"proveedor": "Proveedor inexistente"}, "no existe"),
        ({"tipo_movimiento": "Tipo inexistente"}, "no existe"),
        ({"tipo_movimiento": "Tipo inactivo"}, "inactivo"),
        ({"fecha": "03/11/2019"}, "no existe en el calendario"),
        ({"fecha": "fecha rota"}, "formato"),
    ],
)
def test_errores_por_fila_no_son_importables(cambios, motivo):
    servicio, movimientos = _servicio()

    resultado = servicio.analizar(
        _archivo([_fila_valida(**cambios)]), "movimientos.xlsx"
    )

    assert resultado["validos"] == 0
    assert resultado["con_error"] == 1
    assert motivo.lower() in resultado["errores"][0]["detalle"].lower()
    assert resultado["errores"][0]["registro"] == 2
    assert movimientos.llamadas == 0


def test_duplicado_interno_del_archivo_se_separa():
    servicio, movimientos = _servicio()
    fila = _fila_valida()

    resultado = servicio.analizar(
        _archivo([fila, list(fila)]), "movimientos.xlsx"
    )

    assert resultado["validos"] == 1
    assert resultado["duplicados"] == 1
    assert resultado["errores"][0]["registro"] == 3
    assert "fila 2" in resultado["errores"][0]["detalle"].lower()
    assert movimientos.llamadas == 0


def test_duplicado_de_una_carga_anterior_se_detecta_por_marcador():
    contenido = _archivo([_fila_valida()])
    hash_archivo = hashlib.sha256(contenido).hexdigest()
    servicio, movimientos = _servicio(
        existentes=[f"[INK-IMPORT:{hash_archivo}:2] Compra previa"]
    )

    resultado = servicio.analizar(contenido, "movimientos.xlsx")

    assert resultado["validos"] == 0
    assert resultado["duplicados"] == 1
    assert "ya fue importado" in resultado["errores"][0]["detalle"].lower()
    assert movimientos.llamadas == 0


def test_archivo_sin_hoja_de_movimientos_es_error_de_validacion():
    libro = Workbook()
    libro.active.title = "Otra"
    buffer = BytesIO()
    libro.save(buffer)
    servicio, _ = _servicio()

    with pytest.raises(ValidationError):
        servicio.analizar(buffer.getvalue(), "movimientos.xlsx")


# ----------------------------------------------------------------------
# Formato del reporte real
# ----------------------------------------------------------------------
def test_reconoce_hoja_movimientos_registrados_app():
    servicio, movimientos = _servicio()
    columnas = [
        "fecha",
        "nombre_area",
        "nombre_producto",
        "tipo_movimiento",
        "cantidad",
        "costo_unitario",
        "costo_total",
        "stock_resultante",
        "nombre_evento",
        "rut_usuario",
    ]
    filas = [
        {
            "fecha": "2026-11-03",
            "nombre_area": "Bodega",
            "nombre_producto": "Aceitunas verdes",
            "tipo_movimiento": "Salida",
            "cantidad": 2,
            "costo_unitario": 1500,
            "costo_total": 3000,
            "stock_resultante": 10,
            "nombre_evento": "Evento de prueba",
            "rut_usuario": "999999999",
        }
    ]
    contenido = _archivo_dicts(filas, columnas, hoja=HOJA_MOVIMIENTOS_APP)

    resultado = servicio.analizar(
        contenido, "reporte.xlsx", usuario_rut="123456789"
    )

    assert resultado["hoja"] == HOJA_MOVIMIENTOS_APP
    assert resultado["validos"] == 1
    assert resultado["con_error"] == 0
    texto = " ".join(resultado["advertencias_generales"]).lower()
    assert "stock_resultante" in texto
    assert "costo_total" in texto
    assert "rut_usuario" in texto

    importado = servicio.importar(
        contenido, "reporte.xlsx", "123456789", confirmado=True
    )
    assert importado["importados"] == 1
    payload = movimientos.payloads[0]
    assert payload["id_tipo_movimiento"] == 2
    assert payload["costo_unitario"] == 1500
    assert payload["rut_usuario"] == "123456789"
    assert "Evento: Evento de prueba" in payload["observacion"]
    assert "stock_resultante" not in str(payload)
    assert "costo_total" not in str(payload)


def test_rut_ajeno_se_atribuye_al_importador_y_se_avisa():
    servicio, movimientos = _servicio()
    columnas = list(COLUMNAS) + ["rut_usuario"]
    fila = _fila_valida()
    datos = dict(zip(COLUMNAS, fila))
    datos["rut_usuario"] = "999999999"
    contenido = _archivo_dicts([datos], columnas)

    resultado = servicio.analizar(
        contenido, "movimientos.xlsx", usuario_rut="123456789"
    )

    assert resultado["validos"] == 1
    assert "no coincide con tu sesión" in resultado["filas"][0]["detalle"].lower()

    servicio.importar(
        contenido, "movimientos.xlsx", "123456789", confirmado=True
    )
    assert movimientos.payloads[0]["rut_usuario"] == "123456789"


# ----------------------------------------------------------------------
# Tipos de movimiento y costo
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "tipo,id_tipo",
    [
        ("Entrada", 1),
        ("Salida", 2),
        ("Merma", 3),
        ("Ajuste positivo", 4),
        ("Ajuste negativo", 5),
    ],
)
def test_todos_los_tipos_se_resuelven_desde_el_catalogo(tipo, id_tipo):
    servicio, movimientos = _servicio(
        stock=[
            {
                "id_producto": 1,
                "id_area": 1,
                "cantidad": 50,
                "dim_tipo_movimiento": {"tipo_movimiento": "Entrada", "factor_stock": 1},
            }
        ]
    )

    resultado = servicio.importar(
        _archivo([_fila_valida(tipo_movimiento=tipo)]),
        "movimientos.xlsx",
        "123456789",
        confirmado=True,
    )

    assert resultado["importados"] == 1
    assert movimientos.payloads[0]["id_tipo_movimiento"] == id_tipo


def test_costo_unitario_vacio_usa_costo_base():
    servicio, movimientos = _servicio()

    servicio.importar(
        _archivo([_fila_valida(costo_unitario=None)]),
        "movimientos.xlsx",
        "123456789",
        confirmado=True,
    )

    assert movimientos.payloads[0]["costo_unitario"] == 1200.0


def test_stock_insuficiente_se_detecta_antes_de_escribir():
    servicio, movimientos = _servicio(
        stock=[
            {
                "id_producto": 1,
                "id_area": 1,
                "cantidad": 3,
                "dim_tipo_movimiento": {"tipo_movimiento": "Entrada", "factor_stock": 1},
            }
        ]
    )

    resultado = servicio.analizar(
        _archivo([_fila_valida(tipo_movimiento="Salida", cantidad=5)]),
        "movimientos.xlsx",
    )

    assert resultado["validos"] == 0
    assert resultado["con_error"] == 1
    assert "stock insuficiente" in resultado["errores"][0]["detalle"].lower()
    assert movimientos.llamadas == 0


# ----------------------------------------------------------------------
# Confirmación y registro
# ----------------------------------------------------------------------
def test_importar_sin_confirmacion_no_escribe():
    servicio, movimientos = _servicio()

    with pytest.raises(ValidationError):
        servicio.importar(
            _archivo([_fila_valida()]),
            "movimientos.xlsx",
            "12345678-9",
            confirmado=False,
        )

    assert movimientos.llamadas == 0


def test_importar_valido_registra_movimiento_real_una_sola_vez():
    servicio, movimientos = _servicio()

    resultado = servicio.importar(
        _archivo([_fila_valida()]),
        "movimientos.xlsx",
        "12345678-9",
        confirmado=True,
    )

    assert resultado["importados"] == 1
    assert resultado["rechazados"] == 0
    assert resultado["duplicados"] == 0
    assert movimientos.llamadas == 1
    assert len(movimientos.payloads) == 1

    payload = movimientos.payloads[0]
    assert payload["id_producto"] == 1
    assert payload["id_area"] == 1
    assert payload["id_tipo_movimiento"] == 1
    assert payload["id_fecha"] == 100
    assert payload["cantidad"] == 12
    assert payload["costo_unitario"] == 1500.0
    assert payload["rut_usuario"] == "123456789"
    assert payload["rut_proveedor"] == "109662062"
    assert payload["fecha_hora_registro"]
    assert "[INK-IMPORT:" in payload["observacion"]
    assert "Documento: F-123" in payload["observacion"]
    assert "Compra semanal" in payload["observacion"]


def test_importacion_solo_envia_filas_validas():
    servicio, movimientos = _servicio()
    contenido = _archivo(
        [
            _fila_valida(),
            _fila_valida(cantidad=0),
            _fila_valida(producto="No existe"),
        ]
    )

    resultado = servicio.importar(
        contenido, "movimientos.xlsx", "123456789", confirmado=True
    )

    assert resultado["importados"] == 1
    assert resultado["rechazados"] == 2
    assert len(movimientos.payloads) == 1
    assert len(resultado["errores"]) == 2


def test_importacion_multifila_usa_una_sola_llamada():
    servicio, movimientos = _servicio()
    contenido = _archivo(
        [
            _fila_valida(cantidad=3),
            _fila_valida(cantidad=4, fecha="04/11/2026"),
            _fila_valida(cantidad=5),
        ]
    )

    resultado = servicio.importar(
        contenido, "movimientos.xlsx", "123456789", confirmado=True
    )

    assert resultado["importados"] == 3
    assert len(movimientos.payloads) == 3
    assert movimientos.llamadas == 1


def test_movimientos_importados_alimentan_stock_y_alertas(monkeypatch):
    servicio, movimientos = _servicio()
    contenido = _archivo(
        [
            _fila_valida(cantidad=6),
            _fila_valida(tipo_movimiento="Salida", cantidad=2),
            _fila_valida(tipo_movimiento="Merma", cantidad=1),
        ]
    )

    servicio.importar(
        contenido, "movimientos.xlsx", "123456789", confirmado=True
    )

    tipos_por_id = {
        tipo["id_tipo_movimiento"]: tipo for tipo in TIPOS
    }
    calculados = [
        {
            **payload,
            "dim_tipo_movimiento": tipos_por_id[payload["id_tipo_movimiento"]],
        }
        for payload in movimientos.payloads
    ]
    resumen = resumir_movimientos(calculados)
    datos = resumen[(1, 1)]

    assert datos["stock"] == 3
    assert datos["entradas"] == 6
    assert datos["salidas"] == 2
    assert datos["mermas"] == 1

    fila = {
        "id_producto": 1,
        "nombre": "Aceitunas verdes",
        "categoria": "Insumos",
        "unidad": "kg",
        "stock_actual": datos["stock"],
        "stock_minimo": 10,
        "estado": clasificar_stock(datos["stock"], 10),
    }
    assert fila["estado"] == "Crítico"

    monkeypatch.setattr(
        "data.alertas.inventario_visible", lambda *, usuario=None: [fila]
    )
    monkeypatch.setattr("data.alertas.historial", lambda **kwargs: [])
    monkeypatch.setattr(
        "data.alertas.listar_tipos_movimiento",
        lambda incluir_inactivos=False: list(TIPOS),
    )
    monkeypatch.setattr(
        "data.alertas.listar_areas",
        lambda incluir_inactivas=False: list(AREAS),
    )

    alertas = resumen_alertas(usuario=ADMIN)

    assert alertas["conteos"]["criticos"] == 1
    assert alertas["conteos"]["sin_stock"] == 0
    assert alertas["criticos"][0]["stock_actual"] == 3


def test_fallo_de_insercion_no_deja_registros_parciales():
    servicio, movimientos = _servicio(
        error=RuntimeError("fallo simulado de PostgreSQL")
    )
    contenido = _archivo([_fila_valida(), _fila_valida(cantidad=5)])

    with pytest.raises(RuntimeError):
        servicio.importar(
            contenido, "movimientos.xlsx", "123456789", confirmado=True
        )

    assert movimientos.llamadas == 1
    assert movimientos.payloads is None


# ----------------------------------------------------------------------
# Capa de datos: permisos por rol y confirmación
# ----------------------------------------------------------------------
def test_capa_de_datos_permite_administrador_y_operario(monkeypatch):
    servicio, _ = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)
    contenido = _archivo([_fila_valida()])

    analisis_admin = previsualizar_importacion_inventario(
        contenido, "movimientos.xlsx", usuario=ADMIN
    )
    analisis_operario = previsualizar_importacion_inventario(
        contenido, "movimientos.xlsx", usuario=OPERARIO
    )

    assert analisis_admin["validos"] == 1
    assert analisis_operario["validos"] == 1
    assert generar_plantilla_inventario(usuario=OPERARIO)


def test_capa_de_datos_operario_solo_importa_su_area(monkeypatch):
    servicio, movimientos = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)
    contenido = _archivo([_fila_valida(area="Barra")])

    analisis = previsualizar_importacion_inventario(
        contenido, "movimientos.xlsx", usuario=OPERARIO
    )

    assert analisis["validos"] == 0
    assert analisis["con_error"] == 1
    assert "solo puedes importar" in analisis["errores"][0]["detalle"].lower()
    assert movimientos.llamadas == 0


def test_capa_de_datos_operario_importa_en_su_area(monkeypatch):
    servicio, movimientos = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)

    resultado = importar_entradas_inventario(
        _archivo([_fila_valida()]),
        "movimientos.xlsx",
        confirmado=True,
        usuario=OPERARIO,
    )

    assert resultado["importados"] == 1
    assert movimientos.payloads[0]["rut_usuario"] == "111111111"
    assert movimientos.payloads[0]["id_area"] == 1


def test_capa_de_datos_admin_importa_cualquier_area(monkeypatch):
    servicio, movimientos = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)

    resultado = importar_entradas_inventario(
        _archivo([_fila_valida(area="Barra")]),
        "movimientos.xlsx",
        confirmado=True,
        usuario=ADMIN,
    )

    assert resultado["importados"] == 1
    assert movimientos.payloads[0]["id_area"] == 2


def test_capa_de_datos_invalida_cache_tras_importar(monkeypatch):
    servicio, _ = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)
    limpiezas = {"n": 0}

    def fake_limpiar_cache():
        limpiezas["n"] += 1

    monkeypatch.setattr(
        "data.importacion_inventario.limpiar_cache", fake_limpiar_cache
    )

    importar_entradas_inventario(
        _archivo([_fila_valida()]),
        "movimientos.xlsx",
        confirmado=True,
        usuario=ADMIN,
    )

    assert limpiezas["n"] == 1


def test_capa_de_datos_exige_confirmacion_explicita(monkeypatch):
    servicio, movimientos = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)

    with pytest.raises(ErrorDatos):
        importar_entradas_inventario(
            _archivo([_fila_valida()]),
            "movimientos.xlsx",
            confirmado=False,
            usuario=ADMIN,
        )

    assert movimientos.llamadas == 0


def test_capa_de_datos_exige_sesion(monkeypatch):
    servicio, _ = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)

    with pytest.raises(AuthorizationError):
        previsualizar_importacion_inventario(
            _archivo([_fila_valida()]), "movimientos.xlsx", usuario={}
        )


def test_capa_de_datos_rechaza_archivos_que_no_son_xlsx(monkeypatch):
    servicio, _ = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)

    with pytest.raises(ErrorDatos):
        previsualizar_importacion_inventario(
            b"contenido", "movimientos.csv", usuario=ADMIN
        )


def test_plantilla_de_capa_de_datos_no_escribe(monkeypatch):
    servicio, movimientos = _servicio()
    monkeypatch.setattr("data.importacion_inventario._servicio", lambda: servicio)

    contenido = generar_plantilla_inventario(usuario=ADMIN)

    assert contenido
    assert movimientos.llamadas == 0
