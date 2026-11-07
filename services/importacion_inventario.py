"""Importación de movimientos de inventario desde Excel (.xlsx).

El flujo es: plantilla descargable, lectura de la hoja de movimientos,
validación por fila, vista previa y confirmación explícita. Nada se escribe
antes de la confirmación y la escritura se hace en una sola llamada para no
dejar cargas parciales. No se crean columnas ni productos: solo se usan los
catálogos existentes.

Se aceptan dos formatos:
- La plantilla propia, hoja «Movimientos» (o la histórica «Entradas»).
- El reporte `Movimientos_Registrados_App` con columnas como
  `nombre_producto`, `nombre_area`, `tipo_movimiento`, `rut_usuario`, etc.

Las columnas `stock_resultante` y `costo_total` se reconocen pero se ignoran:
el stock se calcula desde los movimientos y el costo se deriva de la cantidad
por el costo unitario.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from core.areas import resolver_area_id
from core.exceptions import ValidationError
from core.importacion import componer_observacion, crear_marcador, marcador_de
from core.stock import calcular_stock_agregado, normalizar_tipo_movimiento
from core.utils import normalizar_rut
from repositories.base import BaseRepository
from repositories.fechas import FechasRepository
from repositories.movimientos import MovimientosRepository
from repositories.productos import ProductosRepository
from repositories.proveedores import ProveedoresRepository
from repositories.usuarios import UsuariosRepository

HOJA_MOVIMIENTOS = "Movimientos"
HOJA_ENTRADAS = HOJA_MOVIMIENTOS  # compatibilidad con importaciones anteriores
HOJA_ENTRADAS_LEGACY = "Entradas"
HOJA_MOVIMIENTOS_APP = "Movimientos_Registrados_App"
HOJA_INSTRUCCIONES = "Instrucciones"
HOJA_CATALOGOS = "Catálogos"

COLUMNAS = (
    "fecha",
    "producto",
    "area",
    "tipo_movimiento",
    "cantidad",
    "costo_unitario",
    "proveedor",
    "documento",
    "observacion",
)
COLUMNAS_OBLIGATORIAS = ("fecha", "producto", "area", "cantidad")
COLUMNAS_OPCIONALES = (
    "tipo_movimiento",
    "costo_unitario",
    "proveedor",
    "documento",
    "observacion",
)
ETIQUETAS_COLUMNA = {
    "fecha": "Fecha",
    "producto": "Producto",
    "area": "Área",
    "tipo_movimiento": "Tipo de movimiento",
    "cantidad": "Cantidad",
    "costo_unitario": "Costo unitario (CLP)",
    "proveedor": "Proveedor",
    "documento": "Documento",
    "observacion": "Observación",
}
MAX_FILAS = 5000
PATRON_MARCADOR_LIKE = "*INK-IMPORT:*"
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")
ROLES_IMPORTACION = ("Administrador", "Operario")

_ALIAS_COLUMNAS = {
    "fecha": {"fecha", "fecha_movimiento", "fecha_de_movimiento", "fecha_entrada"},
    "producto": {"producto", "nombre_producto", "producto_nombre"},
    "area": {"area", "nombre_area", "area_nombre"},
    "tipo_movimiento": {
        "tipo_movimiento",
        "tipo_de_movimiento",
        "tipo",
        "tipo_mov",
        "movimiento",
    },
    "cantidad": {"cantidad", "cantidad_movimiento", "cantidad_entrada"},
    "costo_unitario": {"costo_unitario", "costo_unitario_clp", "costo"},
    "proveedor": {"proveedor", "nombre_proveedor"},
    "documento": {"documento", "documento_referencia", "n_documento", "numero_documento"},
    "observacion": {"observacion", "detalle", "comentario"},
    "rut_usuario": {"rut_usuario", "rut", "rut_del_usuario", "usuario_rut"},
    "evento": {"nombre_evento", "evento", "nombre_del_evento"},
    # Columnas reconocidas del reporte que no se importan como datos propios.
    "costo_total": {"costo_total", "total"},
    "stock_resultante": {"stock_resultante", "stock_final", "stock"},
}
_CAMPO_POR_ALIAS = {
    alias: campo
    for campo, alias in _ALIAS_COLUMNAS.items()
    for alias in alias
}
_COLUMNAS_IGNORADAS = {
    "costo_total": (
        "La columna «costo_total» se ignora: el costo se calcula con la "
        "cantidad por el costo unitario."
    ),
    "stock_resultante": (
        "La columna «stock_resultante» se ignora: el stock se calcula desde "
        "los movimientos reales."
    ),
}


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _normalizar(valor: Any) -> str:
    """Minúsculas, sin tildes y con espacios simples."""
    texto = unicodedata.normalize("NFKD", _texto(valor))
    sin_tildes = "".join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    )
    return " ".join(sin_tildes.casefold().split())


def _clave_columna(valor: Any) -> str:
    texto = re.sub(r"\([^)]*\)", " ", _normalizar(valor))
    return "_".join(texto.split())


def _fecha_a_texto(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    return texto[:10] if texto else None


def _parsear_fecha(valor: Any) -> Tuple[Optional[date], str]:
    if _vacio(valor):
        return None, "Falta la fecha."
    if isinstance(valor, datetime):
        return valor.date(), ""
    if isinstance(valor, date):
        return valor, ""

    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        try:
            if math.isfinite(float(valor)) and 1 <= float(valor) <= 100000:
                base = datetime(1899, 12, 30)
                return (base + timedelta(days=float(valor))).date(), ""
        except (TypeError, ValueError, OverflowError):
            pass

    texto = str(valor).strip()
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date(), ""
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date(), ""
    except ValueError:
        return None, (
            "La fecha no tiene un formato válido. Usa DD/MM/AAAA o AAAA-MM-DD."
        )


def _parsear_numero(valor: Any) -> Tuple[Optional[float], str]:
    if _vacio(valor):
        return None, ""
    if isinstance(valor, bool):
        return None, "El valor debe ser numérico."
    texto = str(valor).strip().replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        numero = float(texto)
    except (TypeError, ValueError):
        return None, "El valor debe ser numérico."
    if not math.isfinite(numero):
        return None, "El valor debe ser un número finito."
    return numero, ""


def _parsear_cantidad(valor: Any) -> Tuple[Optional[int], str]:
    numero, error = _parsear_numero(valor)
    if error:
        return None, "La cantidad debe ser un número."
    if numero is None:
        return None, "Falta la cantidad."
    if numero <= 0:
        return None, "La cantidad debe ser mayor que cero."
    if not float(numero).is_integer():
        return None, "La cantidad debe ser un número entero."
    return int(numero), ""


def _parsear_costo(valor: Any) -> Tuple[Optional[float], str]:
    numero, error = _parsear_numero(valor)
    if error:
        return None, "El costo unitario debe ser un número."
    if numero is None:
        return None, ""
    if numero < 0:
        return None, "El costo unitario no puede ser negativo."
    return numero, ""


def _rut_archivo(valor: Any) -> Optional[str]:
    """Normaliza el RUT del archivo; None si está vacío o es inválido."""
    texto = _texto(valor)
    if not texto:
        return None
    try:
        return normalizar_rut(texto)
    except Exception:
        return None


class ImportacionInventarioService:
    def __init__(
        self,
        *,
        productos_repo: Optional[Any] = None,
        areas_repo: Optional[Any] = None,
        proveedores_repo: Optional[Any] = None,
        tipos_repo: Optional[Any] = None,
        fechas_repo: Optional[Any] = None,
        movimientos_repo: Optional[Any] = None,
        usuarios_repo: Optional[Any] = None,
    ) -> None:
        self.productos_repo = productos_repo or ProductosRepository()
        self.areas_repo = areas_repo or BaseRepository("dim_area")
        self.proveedores_repo = proveedores_repo or ProveedoresRepository()
        self.tipos_repo = tipos_repo or BaseRepository("dim_tipo_movimiento")
        self.fechas_repo = fechas_repo or FechasRepository()
        self.movimientos_repo = movimientos_repo or MovimientosRepository()
        self.usuarios_repo = usuarios_repo or UsuariosRepository()

    # ------------------------------------------------------------------
    # Plantilla
    # ------------------------------------------------------------------
    def generar_plantilla(self) -> bytes:
        """Genera la plantilla con hoja Movimientos, formatos y listas reales."""
        productos = self.productos_repo.get_all({"activo": True}) or []
        areas = self.areas_repo.get_all({"activo": True}) or []
        proveedores = self.proveedores_repo.get_all({"activo": True}) or []
        tipos = [
            tipo
            for tipo in (self.tipos_repo.get_all({"activo": True}) or [])
            if tipo.get("activo", True)
        ]

        productos = sorted(
            productos, key=lambda fila: _normalizar(fila.get("nombre_producto"))
        )
        areas = sorted(areas, key=lambda fila: _normalizar(fila.get("nombre_area")))
        proveedores = sorted(
            proveedores, key=lambda fila: _normalizar(fila.get("nombre_proveedor"))
        )
        tipos = sorted(
            tipos, key=lambda fila: _normalizar(fila.get("tipo_movimiento"))
        )

        libro = Workbook()
        hoja = libro.active
        hoja.title = HOJA_MOVIMIENTOS
        self._escribir_encabezados(hoja)
        self._escribir_listas(libro, productos, areas, proveedores, tipos)
        self._escribir_instrucciones(libro, productos, areas, proveedores, tipos)
        self._aplicar_validaciones(hoja, productos, areas, proveedores, tipos)

        buffer = BytesIO()
        libro.save(buffer)
        return buffer.getvalue()

    def _escribir_encabezados(self, hoja) -> None:
        relleno = PatternFill("solid", fgColor="5B2333")
        fuente = Font(color="FFFFFF", bold=True)
        for indice, columna in enumerate(COLUMNAS, start=1):
            celda = hoja.cell(row=1, column=indice, value=ETIQUETAS_COLUMNA[columna])
            celda.fill = relleno
            celda.font = fuente
            celda.alignment = Alignment(horizontal="center", vertical="center")
            hoja.column_dimensions[celda.column_letter].width = 22
        hoja.freeze_panes = "A2"
        hoja.row_dimensions[1].height = 24
        for fila in range(2, MAX_FILAS + 2):
            hoja.cell(row=fila, column=1).number_format = "DD-MM-YYYY"
            hoja.cell(row=fila, column=6).number_format = "#,##0.00"

    def _escribir_listas(
        self,
        libro: Workbook,
        productos: List[Dict[str, Any]],
        areas: List[Dict[str, Any]],
        proveedores: List[Dict[str, Any]],
        tipos: List[Dict[str, Any]],
    ) -> None:
        hoja = libro.create_sheet(HOJA_CATALOGOS)
        encabezados = (
            "Producto",
            "Área",
            "Proveedor",
            "RUT proveedor",
            "Tipo de movimiento",
            "Factor de stock",
        )
        for indice, titulo in enumerate(encabezados, start=1):
            celda = hoja.cell(row=1, column=indice, value=titulo)
            celda.font = Font(bold=True)
            hoja.column_dimensions[celda.column_letter].width = 30

        maximo = max(
            len(productos), len(areas), len(proveedores), len(tipos), 1
        )
        for posicion in range(maximo):
            fila = posicion + 2
            if posicion < len(productos):
                hoja.cell(
                    row=fila,
                    column=1,
                    value=str(productos[posicion].get("nombre_producto") or ""),
                )
            if posicion < len(areas):
                hoja.cell(
                    row=fila,
                    column=2,
                    value=str(areas[posicion].get("nombre_area") or ""),
                )
            if posicion < len(proveedores):
                hoja.cell(
                    row=fila,
                    column=3,
                    value=str(
                        proveedores[posicion].get("nombre_proveedor") or ""
                    ),
                )
                hoja.cell(
                    row=fila,
                    column=4,
                    value=str(proveedores[posicion].get("rut_proveedor") or ""),
                )
            if posicion < len(tipos):
                hoja.cell(
                    row=fila,
                    column=5,
                    value=str(tipos[posicion].get("tipo_movimiento") or ""),
                )
                hoja.cell(
                    row=fila,
                    column=6,
                    value=tipos[posicion].get("factor_stock"),
                )

    def _escribir_instrucciones(
        self,
        libro: Workbook,
        productos: List[Dict[str, Any]],
        areas: List[Dict[str, Any]],
        proveedores: List[Dict[str, Any]],
        tipos: List[Dict[str, Any]],
    ) -> None:
        hoja = libro.create_sheet(HOJA_INSTRUCCIONES)
        hoja.column_dimensions["A"].width = 30
        hoja.column_dimensions["B"].width = 16
        hoja.column_dimensions["C"].width = 34
        hoja.column_dimensions["D"].width = 48

        lineas = [
            "Plantilla de importación de movimientos de inventario",
            "",
            "Usa únicamente la hoja «Movimientos». Cada fila es un movimiento independiente.",
            "También se acepta el reporte «Movimientos_Registrados_App» con sus columnas.",
            "No cambies los encabezados ni agregues filas de ejemplo a la hoja Movimientos.",
            "Los productos, áreas, tipos y proveedores se eligen de las listas desplegables.",
            "El costo unitario puede quedar vacío: se usará el costo base del producto.",
            "Las columnas stock_resultante y costo_total se ignoran: se recalculan.",
            "Si el archivo trae rut_usuario distinto a tu sesión, el movimiento se atribuye a ti.",
            "Nada se guarda hasta que confirmes la importación en la aplicación.",
            "",
        ]
        for indice, texto in enumerate(lineas, start=1):
            hoja.cell(row=indice, column=1, value=texto)

        fila_cabecera = len(lineas) + 1
        for indice, titulo in enumerate(
            ("Columna", "Obligatoria", "Formato", "Ejemplo / nota"), start=1
        ):
            celda = hoja.cell(row=fila_cabecera, column=indice, value=titulo)
            celda.font = Font(bold=True)

        detalle = [
            (
                "fecha",
                "Sí",
                "DD/MM/AAAA o AAAA-MM-DD",
                "Debe existir en el calendario del sistema.",
            ),
            (
                "producto",
                "Sí",
                "Nombre exacto del catálogo",
                "Elige de la lista desplegable; no se crean productos.",
            ),
            (
                "area",
                "Sí",
                "Nombre exacto del catálogo",
                "Un operario solo puede importar en su área asignada.",
            ),
            (
                "tipo_movimiento",
                "No",
                "Nombre exacto del catálogo",
                "Entrada, Salida, Merma, Ajuste positivo o Ajuste negativo. Si falta, se usa Entrada.",
            ),
            (
                "cantidad",
                "Sí",
                "Entero mayor que 0",
                "Siempre positiva: el tipo de movimiento define el signo.",
            ),
            (
                "costo_unitario",
                "No",
                "Número mayor o igual a 0",
                "Si se omite, se usa el costo base del producto.",
            ),
            (
                "proveedor",
                "No",
                "Nombre o RUT del catálogo",
                "Si se informa, debe existir y estar activo.",
            ),
            (
                "documento",
                "No",
                "Texto",
                "Se guarda como referencia dentro de la observación.",
            ),
            (
                "observacion",
                "No",
                "Texto",
                "Se conserva junto con el documento y el marcador interno.",
            ),
        ]
        for desplazamiento, fila_datos in enumerate(detalle, start=1):
            for indice, valor in enumerate(fila_datos, start=1):
                hoja.cell(
                    row=fila_cabecera + desplazamiento,
                    column=indice,
                    value=valor,
                )

        fila_final = fila_cabecera + len(detalle) + 2
        hoja.cell(
            row=fila_final,
            column=1,
            value=f"Productos activos disponibles: {len(productos)}",
        )
        hoja.cell(
            row=fila_final + 1,
            column=1,
            value=f"Áreas activas disponibles: {len(areas)}",
        )
        hoja.cell(
            row=fila_final + 2,
            column=1,
            value=f"Proveedores activos disponibles: {len(proveedores)}",
        )
        hoja.cell(
            row=fila_final + 3,
            column=1,
            value=f"Tipos de movimiento activos disponibles: {len(tipos)}",
        )
        hoja.cell(
            row=fila_final + 5,
            column=1,
            value=(
                "Esta plantilla no contiene productos ficticios ni registros "
                "de prueba. Las listas provienen del catálogo real."
            ),
        )

    def _aplicar_validaciones(
        self,
        hoja,
        productos: List[Dict[str, Any]],
        areas: List[Dict[str, Any]],
        proveedores: List[Dict[str, Any]],
        tipos: List[Dict[str, Any]],
    ) -> None:
        ultima = MAX_FILAS + 1
        validaciones = []

        if productos:
            dv = DataValidation(
                type="list",
                formula1=f"='{HOJA_CATALOGOS}'!$A$2:$A${len(productos) + 1}",
                allow_blank=True,
            )
            validaciones.append((dv, f"B2:B{ultima}"))
        if areas:
            dv = DataValidation(
                type="list",
                formula1=f"='{HOJA_CATALOGOS}'!$B$2:$B${len(areas) + 1}",
                allow_blank=True,
            )
            validaciones.append((dv, f"C2:C{ultima}"))
        if tipos:
            dv = DataValidation(
                type="list",
                formula1=f"='{HOJA_CATALOGOS}'!$E$2:$E${len(tipos) + 1}",
                allow_blank=True,
            )
            validaciones.append((dv, f"D2:D{ultima}"))
        if proveedores:
            dv = DataValidation(
                type="list",
                formula1=f"='{HOJA_CATALOGOS}'!$C$2:$C${len(proveedores) + 1}",
                allow_blank=True,
            )
            validaciones.append((dv, f"G2:G{ultima}"))

        dv_fecha = DataValidation(
            type="date",
            operator="between",
            formula1="DATE(2000,1,1)",
            formula2="DATE(2100,12,31)",
            allow_blank=True,
        )
        validaciones.append((dv_fecha, f"A2:A{ultima}"))

        dv_cantidad = DataValidation(
            type="whole",
            operator="greaterThan",
            formula1="0",
            allow_blank=True,
        )
        validaciones.append((dv_cantidad, f"E2:E{ultima}"))

        dv_costo = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0",
            allow_blank=True,
        )
        validaciones.append((dv_costo, f"F2:F{ultima}"))

        for dv, rango in validaciones:
            hoja.add_data_validation(dv)
            dv.add(rango)

    # ------------------------------------------------------------------
    # Lectura y validación
    # ------------------------------------------------------------------
    def _mapear_encabezado(self, valores: Iterable[Any]) -> Dict[str, int]:
        indices: Dict[str, int] = {}
        for indice, valor in enumerate(valores or ()):
            campo = _CAMPO_POR_ALIAS.get(_clave_columna(valor))
            if campo and campo not in indices:
                indices[campo] = indice
        return indices

    def _buscar_encabezado(self, hoja) -> Tuple[Optional[int], Dict[str, int]]:
        for numero, valores in enumerate(
            hoja.iter_rows(min_row=1, max_row=10, values_only=True), start=1
        ):
            indices = self._mapear_encabezado(valores)
            if all(campo in indices for campo in COLUMNAS_OBLIGATORIAS):
                return numero, indices
        return None, {}

    def _leer_hoja(
        self, contenido: bytes
    ) -> Tuple[List[Dict[str, Any]], List[str], List[str], List[str], str]:
        try:
            libro = load_workbook(
                BytesIO(contenido), read_only=True, data_only=True
            )
        except Exception as exc:
            raise ValidationError(
                "No se pudo leer el archivo Excel. Verifica que sea un .xlsx "
                "válido y que no esté dañado."
            ) from exc

        preferidas = (
            HOJA_MOVIMIENTOS,
            HOJA_ENTRADAS_LEGACY,
            HOJA_MOVIMIENTOS_APP,
        )
        ordenadas = list(preferidas) + [
            nombre for nombre in libro.sheetnames if nombre not in preferidas
        ]

        hoja = None
        nombre_hoja = ""
        fila_encabezado = None
        indices: Dict[str, int] = {}
        for nombre in ordenadas:
            if nombre not in libro.sheetnames:
                continue
            candidata = libro[nombre]
            numero, encontrados = self._buscar_encabezado(candidata)
            if numero is not None:
                hoja = candidata
                nombre_hoja = nombre
                fila_encabezado = numero
                indices = encontrados
                break

        if hoja is None or fila_encabezado is None:
            libro.close()
            raise ValidationError(
                "No se encontró una hoja con las columnas mínimas de "
                "movimientos (fecha, producto, área y cantidad). Descarga la "
                "plantilla o usa la hoja «Movimientos_Registrados_App»."
            )

        columnas_faltantes = [
            campo for campo in COLUMNAS_OPCIONALES if campo not in indices
        ]

        advertencias: List[str] = []
        for campo, mensaje in _COLUMNAS_IGNORADAS.items():
            if campo in indices:
                advertencias.append(mensaje)
        if "rut_usuario" in indices:
            advertencias.append(
                "El archivo incluye «rut_usuario»: solo se acepta si coincide "
                "con tu sesión. Si no coincide, el movimiento se atribuye a ti."
            )

        filas: List[Dict[str, Any]] = []
        for numero, valores in enumerate(
            hoja.iter_rows(min_row=fila_encabezado + 1, values_only=True),
            start=fila_encabezado + 1,
        ):
            valores = tuple(valores or ())
            if all(_vacio(valor) for valor in valores):
                filas.append({"registro": numero, "vacia": True, "datos": {}})
                continue
            datos = {
                campo: valores[indice] if indice < len(valores) else None
                for campo, indice in indices.items()
            }
            filas.append({"registro": numero, "vacia": False, "datos": datos})

        libro.close()
        # La plantilla puede traer filas con solo formato al final. No cuentan
        # como filas del archivo ni como errores.
        while filas and filas[-1]["vacia"]:
            filas.pop()
        return filas, list(indices), columnas_faltantes, advertencias, nombre_hoja

    def _catalogos(self) -> Dict[str, Any]:
        productos = self.productos_repo.get_all(None) or []
        areas = self.areas_repo.get_all(None) or []
        proveedores = self.proveedores_repo.get_all(None) or []
        tipos = self.tipos_repo.get_all(None) or []

        tipos_por_nombre: Dict[str, List[Dict[str, Any]]] = {}
        for tipo in tipos:
            clave = normalizar_tipo_movimiento(tipo.get("tipo_movimiento"))
            if clave:
                tipos_por_nombre.setdefault(clave, []).append(tipo)

        tipo_entrada = next(
            (
                tipo
                for tipo in tipos_por_nombre.get("entrada", [])
                if tipo.get("activo", True)
                and str(tipo.get("factor_stock")) in {"1", "1.0"}
            ),
            None,
        )

        return {
            "productos": productos,
            "areas": areas,
            "proveedores": proveedores,
            "tipos": tipos,
            "tipos_por_nombre": tipos_por_nombre,
            "tipo_entrada": tipo_entrada,
        }

    def _indices_productos(self, productos: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        indice: Dict[str, List[Dict[str, Any]]] = {}
        for producto in productos:
            clave = _normalizar(producto.get("nombre_producto"))
            if clave:
                indice.setdefault(clave, []).append(producto)
        return indice

    def _indices_areas(self, areas: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        indice: Dict[str, List[Dict[str, Any]]] = {}
        for area in areas:
            clave = _normalizar(area.get("nombre_area"))
            if clave:
                indice.setdefault(clave, []).append(area)
        return indice

    def _indices_proveedores(
        self, proveedores: Iterable[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        indice: Dict[str, List[Dict[str, Any]]] = {}
        for proveedor in proveedores:
            for valor in (
                proveedor.get("nombre_proveedor"),
                proveedor.get("rut_proveedor"),
            ):
                clave = _normalizar(valor)
                if clave:
                    indice.setdefault(clave, []).append(proveedor)
        return indice

    def _marcadores_existentes(self) -> set:
        metodo = getattr(self.movimientos_repo, "observaciones_con_marcador", None)
        if not metodo:
            return set()
        observaciones = metodo(PATRON_MARCADOR_LIKE) or []
        marcadores = set()
        for observacion in observaciones:
            marcador = marcador_de(observacion)
            if marcador:
                marcadores.add(marcador)
        return marcadores

    def _resolver_tipo(
        self,
        tipo_texto: str,
        tipos_por_nombre: Dict[str, List[Dict[str, Any]]],
        tipo_por_defecto: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Resuelve el tipo por nombre y valida que tenga factor +1 o -1."""
        if not tipo_texto:
            if not tipo_por_defecto:
                return None, (
                    "Falta el tipo de movimiento y no hay un tipo «Entrada» "
                    "activo para usarlo por defecto."
                )
            return tipo_por_defecto, ""

        candidatos = tipos_por_nombre.get(
            normalizar_tipo_movimiento(tipo_texto), []
        )
        if not candidatos:
            return None, (
                f"El tipo de movimiento «{tipo_texto}» no existe en el catálogo."
            )
        activos = [tipo for tipo in candidatos if tipo.get("activo", True)]
        if not activos:
            return None, (
                f"El tipo de movimiento «{tipo_texto}» está inactivo."
            )
        if len(activos) > 1:
            return None, (
                f"Hay más de un tipo de movimiento llamado «{tipo_texto}». "
                "Usa un nombre único en el catálogo."
            )

        tipo = activos[0]
        try:
            factor = int(float(tipo.get("factor_stock")))
        except (TypeError, ValueError):
            factor = 0
        if factor not in (1, -1):
            return None, (
                f"El tipo de movimiento «{tipo_texto}» no tiene un factor de "
                "stock válido (+1 o -1)."
            )
        return tipo, ""

    def _resolver_importador(
        self, usuario_rut: Optional[str]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Valida el usuario autenticado que ejecuta la importación."""
        if not usuario_rut:
            return None, None

        texto = _texto(usuario_rut)
        if not texto:
            raise ValidationError(
                "Tu sesión no tiene un usuario válido. Vuelve a iniciar sesión."
            )
        try:
            rut = normalizar_rut(texto)
        except Exception as exc:
            raise ValidationError(
                "El RUT de tu sesión no es válido. Vuelve a iniciar sesión."
            ) from exc

        usuario = self.usuarios_repo.get_by_rut(rut)
        if not usuario:
            raise ValidationError("Tu usuario no existe en el catálogo.")
        if not usuario.get("activo", False):
            raise ValidationError("Tu usuario está inactivo y no puede importar.")
        if usuario.get("rol") not in ROLES_IMPORTACION:
            raise ValidationError(
                "Tu perfil no tiene permisos para importar movimientos."
            )
        return usuario, rut

    def _stock_inicial(self) -> Optional[Dict[Tuple[int, int], float]]:
        """Stock actual para simular el archivo, si el repositorio lo permite."""
        metodo = getattr(self.movimientos_repo, "stock_agregado", None)
        if not metodo:
            return None
        try:
            return calcular_stock_agregado(metodo())
        except Exception:
            return None

    def _evaluar(
        self,
        contenido: bytes,
        *,
        incluir_registros: bool = False,
        usuario_rut: Optional[str] = None,
    ) -> Dict[str, Any]:
        hash_archivo = hashlib.sha256(contenido).hexdigest()
        (
            filas_crudas,
            columnas,
            columnas_faltantes,
            advertencias_columnas,
            nombre_hoja,
        ) = self._leer_hoja(contenido)
        catalogos = self._catalogos()
        usuario_importador, rut_importador = self._resolver_importador(
            usuario_rut
        )

        productos = self._indices_productos(catalogos["productos"])
        areas = self._indices_areas(catalogos["areas"])
        proveedores = self._indices_proveedores(catalogos["proveedores"])
        tipos_por_nombre = catalogos["tipos_por_nombre"]
        tipo_entrada = catalogos["tipo_entrada"]

        es_admin = bool(usuario_importador) and (
            usuario_importador.get("rol") == "Administrador"
        )
        area_propia_id = None
        area_propia_nombre = ""
        if usuario_importador and not es_admin:
            area_propia_id = resolver_area_id(
                usuario_importador.get("area_asignada"),
                catalogos["areas"],
            )
            if area_propia_id is not None:
                for area in catalogos["areas"]:
                    try:
                        if int(area.get("id_area")) == int(area_propia_id):
                            area_propia_nombre = str(
                                area.get("nombre_area") or ""
                            )
                            break
                    except (TypeError, ValueError):
                        continue

        fechas = [
            _parsear_fecha(fila["datos"].get("fecha"))[0]
            for fila in filas_crudas
            if not fila["vacia"]
        ]
        ids_fecha = self.fechas_repo.ids_por_fechas(
            [fecha for fecha in fechas if fecha is not None]
        )
        marcadores_existentes = self._marcadores_existentes()
        stock_inicial = self._stock_inicial()
        stock_simulado = dict(stock_inicial or {})

        errores_generales: List[str] = list(advertencias_columnas)
        for campo in columnas_faltantes:
            if campo == "tipo_movimiento":
                errores_generales.append(
                    "El archivo no incluye la columna «Tipo de movimiento»: "
                    "las filas se registrarán como Entrada. Agrega la columna "
                    "para importar salidas, mermas o ajustes."
                )
            else:
                errores_generales.append(
                    f"El archivo no incluye la columna «{ETIQUETAS_COLUMNA[campo]}»: "
                    "ese dato no se guardará. Si lo necesitas, agrega la columna y "
                    "vuelve a cargar el archivo."
                )

        if len(filas_crudas) > MAX_FILAS:
            raise ValidationError(
                f"El archivo supera el máximo de {MAX_FILAS} filas por "
                "importación. Divide el archivo en partes más pequeñas."
            )

        filas: List[Dict[str, Any]] = []
        errores: List[Dict[str, Any]] = []
        registros_validos: List[Dict[str, Any]] = []
        vistos: Dict[str, int] = {}
        total_filas = len(filas_crudas)
        filas_vacias = 0
        validos = 0
        con_error = 0
        duplicados = 0

        for fila_cruda in filas_crudas:
            numero = int(fila_cruda["registro"])
            if fila_cruda["vacia"]:
                filas_vacias += 1
                continue

            datos = fila_cruda["datos"]
            errores_fila: List[str] = []
            notas: List[str] = []

            fecha, error_fecha = _parsear_fecha(datos.get("fecha"))
            if error_fecha:
                errores_fila.append(error_fecha)
            fecha_texto = fecha.isoformat() if fecha else ""

            producto_texto = _texto(datos.get("producto"))
            producto = None
            if not producto_texto:
                errores_fila.append("Falta el producto.")
            else:
                candidatos = productos.get(_normalizar(producto_texto), [])
                if not candidatos:
                    errores_fila.append(
                        f"El producto «{producto_texto}» no existe en el catálogo."
                    )
                elif len(candidatos) > 1:
                    errores_fila.append(
                        f"Hay más de un producto llamado «{producto_texto}». "
                        "Usa un nombre único en el catálogo."
                    )
                else:
                    producto = candidatos[0]
                    if not producto.get("activo", True):
                        errores_fila.append(
                            f"El producto «{producto_texto}» está inactivo."
                        )

            area_texto = _texto(datos.get("area"))
            area = None
            if not area_texto:
                errores_fila.append("Falta el área.")
            else:
                candidatos_area = areas.get(_normalizar(area_texto), [])
                if not candidatos_area:
                    errores_fila.append(
                        f"El área «{area_texto}» no existe en el catálogo."
                    )
                elif len(candidatos_area) > 1:
                    errores_fila.append(
                        f"Hay más de un área llamada «{area_texto}»."
                    )
                else:
                    area = candidatos_area[0]
                    if not area.get("activo", True):
                        errores_fila.append(
                            f"El área «{area_texto}» está inactiva."
                        )

            if usuario_importador and not es_admin:
                if area_propia_id is None:
                    errores_fila.append(
                        "Tu cuenta no tiene un área válida asignada. Contacta "
                        "al administrador."
                    )
                elif area is not None:
                    try:
                        permitida = int(area.get("id_area")) == int(
                            area_propia_id
                        )
                    except (TypeError, ValueError):
                        permitida = False
                    if not permitida:
                        nombre_propio = area_propia_nombre or "tu área asignada"
                        errores_fila.append(
                            "Solo puedes importar movimientos del área "
                            f"«{nombre_propio}». La fila indica "
                            f"«{area_texto}»."
                        )

            cantidad, error_cantidad = _parsear_cantidad(datos.get("cantidad"))
            if error_cantidad:
                errores_fila.append(error_cantidad)

            costo, error_costo = _parsear_costo(datos.get("costo_unitario"))
            if error_costo:
                errores_fila.append(error_costo)
            if costo is None and producto is not None:
                try:
                    costo = float(producto.get("costo_base") or 0)
                except (TypeError, ValueError):
                    costo = 0.0

            tipo_texto = _texto(datos.get("tipo_movimiento"))
            tipo, error_tipo = self._resolver_tipo(
                tipo_texto, tipos_por_nombre, tipo_entrada
            )
            if error_tipo:
                errores_fila.append(error_tipo)

            proveedor_texto = _texto(datos.get("proveedor"))
            proveedor: Optional[Dict[str, Any]] = None
            if proveedor_texto:
                candidatos_proveedor = proveedores.get(
                    _normalizar(proveedor_texto), []
                )
                if not candidatos_proveedor:
                    errores_fila.append(
                        f"El proveedor «{proveedor_texto}» no existe en el catálogo."
                    )
                elif len(candidatos_proveedor) > 1:
                    errores_fila.append(
                        f"Hay más de un proveedor que coincide con "
                        f"«{proveedor_texto}»."
                    )
                else:
                    proveedor = candidatos_proveedor[0]
                    if not proveedor.get("activo", True):
                        errores_fila.append(
                            f"El proveedor «{proveedor_texto}» está inactivo."
                        )

            documento = _texto(datos.get("documento"))
            observacion = _texto(datos.get("observacion"))
            evento = _texto(datos.get("evento"))
            id_fecha = ids_fecha.get(fecha_texto) if fecha_texto else None
            if fecha and not id_fecha:
                errores_fila.append(
                    f"La fecha {fecha.strftime('%d/%m/%Y')} no existe en el "
                    "calendario del sistema. Revisa la fecha o carga el "
                    "calendario correspondiente."
                )

            rut_declarado = _rut_archivo(datos.get("rut_usuario"))
            if usuario_importador:
                rut_final = rut_importador
                if _texto(datos.get("rut_usuario")) and rut_declarado != rut_importador:
                    notas.append(
                        "El RUT del archivo no coincide con tu sesión; el "
                        "movimiento se atribuye a tu usuario."
                    )
            else:
                rut_final = rut_declarado or ""

            observacion_partes = []
            if evento:
                observacion_partes.append(f"Evento: {evento}")
            if observacion:
                observacion_partes.append(observacion)
            observacion_compuesta = " · ".join(observacion_partes)

            marcador = crear_marcador(hash_archivo, numero)
            contenido_hash = hashlib.sha256(
                json.dumps(
                    [
                        fecha_texto,
                        int(producto.get("id_producto")) if producto else None,
                        int(area.get("id_area")) if area else None,
                        int(tipo.get("id_tipo_movimiento")) if tipo else None,
                        cantidad,
                        costo,
                        _normalizar(proveedor_texto),
                        _normalizar(documento),
                        _normalizar(observacion_compuesta),
                        _normalizar(rut_final),
                    ],
                    ensure_ascii=False,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()

            tipo_nombre = (
                str(tipo.get("tipo_movimiento") or "") if tipo else tipo_texto
            )
            responsable = (
                str(usuario_importador.get("nombre_usuario") or rut_final or "")
                if usuario_importador
                else rut_final
            )

            if (hash_archivo, numero) in marcadores_existentes:
                duplicados += 1
                detalle = (
                    "Este archivo ya fue importado y esta fila ya tiene un "
                    "movimiento registrado."
                )
                errores.append(
                    {
                        "registro": numero,
                        "producto": producto_texto or "—",
                        "fecha": fecha_texto or "—",
                        "detalle": detalle,
                    }
                )
                filas.append(
                    self._fila_resultado(
                        numero, "duplicado", fecha_texto, producto_texto,
                        area_texto, cantidad, costo, proveedor_texto, detalle,
                        tipo=tipo_nombre, responsable=responsable,
                    )
                )
                continue

            if contenido_hash in vistos:
                duplicados += 1
                detalle = (
                    "Repite los mismos datos de la fila "
                    f"{vistos[contenido_hash]} del archivo."
                )
                errores.append(
                    {
                        "registro": numero,
                        "producto": producto_texto or "—",
                        "fecha": fecha_texto or "—",
                        "detalle": detalle,
                    }
                )
                filas.append(
                    self._fila_resultado(
                        numero, "duplicado", fecha_texto, producto_texto,
                        area_texto, cantidad, costo, proveedor_texto, detalle,
                        tipo=tipo_nombre, responsable=responsable,
                    )
                )
                continue

            if errores_fila:
                con_error += 1
                detalle = " ".join(errores_fila)
                errores.append(
                    {
                        "registro": numero,
                        "producto": producto_texto or "—",
                        "fecha": fecha_texto or "—",
                        "detalle": detalle,
                    }
                )
                filas.append(
                    self._fila_resultado(
                        numero, "error", fecha_texto, producto_texto,
                        area_texto, cantidad, costo, proveedor_texto, detalle,
                        tipo=tipo_nombre, responsable=responsable,
                    )
                )
                continue

            if (
                stock_inicial is not None
                and producto is not None
                and area is not None
                and tipo is not None
                and cantidad is not None
            ):
                try:
                    factor = int(float(tipo.get("factor_stock")))
                except (TypeError, ValueError):
                    factor = 0
                llave = (
                    int(producto.get("id_producto")),
                    int(area.get("id_area")),
                )
                disponible = float(stock_simulado.get(llave, 0.0))
                resultante = disponible + (factor * int(cantidad))
                if resultante < 0:
                    con_error += 1
                    detalle = (
                        "Stock insuficiente: el movimiento dejaría el stock en "
                        f"{resultante:g}. Revisa la cantidad o registra primero "
                        "una entrada."
                    )
                    errores.append(
                        {
                            "registro": numero,
                            "producto": producto_texto or "—",
                            "fecha": fecha_texto or "—",
                            "detalle": detalle,
                        }
                    )
                    filas.append(
                        self._fila_resultado(
                            numero, "error", fecha_texto, producto_texto,
                            area_texto, cantidad, costo, proveedor_texto,
                            detalle, tipo=tipo_nombre,
                            responsable=responsable,
                        )
                    )
                    continue
                stock_simulado[llave] = resultante

            vistos[contenido_hash] = numero
            validos += 1
            detalle_valido = " ".join(notas) if notas else ""
            filas.append(
                self._fila_resultado(
                    numero, "valido", fecha_texto, producto_texto,
                    area_texto, cantidad, costo, proveedor_texto,
                    detalle_valido, tipo=tipo_nombre,
                    responsable=responsable,
                )
            )

            if incluir_registros:
                registros_validos.append(
                    {
                        "marcador": marcador,
                        "payload": {
                            "id_fecha": id_fecha,
                            "id_producto": int(producto["id_producto"]),
                            "id_area": int(area["id_area"]),
                            "id_tipo_movimiento": int(
                                tipo["id_tipo_movimiento"]
                            ),
                            "cantidad": cantidad,
                            "costo_unitario": costo,
                            "rut_usuario": rut_final,
                            "observacion": componer_observacion(
                                marcador, documento, observacion_compuesta
                            ),
                            "rut_proveedor": (
                                str(proveedor.get("rut_proveedor"))
                                if proveedor
                                else None
                            ),
                        },
                    }
                )

        resultado: Dict[str, Any] = {
            "nombre_archivo": "",
            "hoja": nombre_hoja,
            "hash_archivo": hash_archivo,
            "columnas": columnas,
            "columnas_faltantes": [
                ETIQUETAS_COLUMNA[campo] for campo in columnas_faltantes
            ],
            "total_filas": total_filas,
            "filas_vacias": filas_vacias,
            "total_consideradas": total_filas - filas_vacias,
            "validos": validos,
            "con_error": con_error,
            "duplicados": duplicados,
            "importables": validos,
            "filas": filas,
            "errores": errores,
            "advertencias_generales": errores_generales,
        }
        if incluir_registros:
            resultado["registros_validos"] = registros_validos
        return resultado

    def _fila_resultado(
        self,
        numero: int,
        estado: str,
        fecha: str,
        producto: str,
        area: str,
        cantidad: Optional[int],
        costo: Optional[float],
        proveedor: str,
        detalle: str,
        *,
        tipo: str = "",
        responsable: str = "",
    ) -> Dict[str, Any]:
        return {
            "registro": numero,
            "estado": estado,
            "fecha": fecha or "—",
            "producto": producto or "—",
            "area": area or "—",
            "tipo": tipo or "—",
            "cantidad": cantidad,
            "costo_unitario": costo,
            "proveedor": proveedor or "—",
            "responsable": responsable or "—",
            "detalle": detalle or "—",
        }

    def analizar(
        self,
        contenido: bytes,
        nombre: str = "",
        usuario_rut: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Valida el archivo completo sin escribir nada en la base."""
        resultado = self._evaluar(
            contenido,
            incluir_registros=False,
            usuario_rut=usuario_rut,
        )
        resultado["nombre_archivo"] = nombre
        resultado["validos"] = resultado["importables"]
        return resultado

    def importar(
        self,
        contenido: bytes,
        nombre: str,
        usuario_rut: str,
        *,
        confirmado: bool = False,
    ) -> Dict[str, Any]:
        """Importa las filas válidas en una sola operación atómica."""
        if not confirmado:
            raise ValidationError(
                "Debes confirmar explícitamente la importación antes de "
                "continuar."
            )

        resultado = self._evaluar(
            contenido,
            incluir_registros=True,
            usuario_rut=usuario_rut,
        )
        resultado["nombre_archivo"] = nombre
        validos = resultado.get("registros_validos") or []
        if not validos:
            raise ValidationError(
                "No hay filas válidas para importar. Revisa los errores y "
                "duplicados de la vista previa."
            )

        marca_tiempo = datetime.now().isoformat()
        payload = []
        for registro in validos:
            fila = dict(registro["payload"])
            fila["fecha_hora_registro"] = marca_tiempo
            if not fila.get("rut_proveedor"):
                fila.pop("rut_proveedor", None)
            payload.append(fila)

        creados = self.movimientos_repo.create_many(payload)
        resultado["importados"] = len(creados) if creados else len(payload)
        resultado["rechazados"] = resultado.get("con_error", 0)
        resultado["duplicados"] = resultado.get("duplicados", 0)
        resultado["filas_vacias"] = resultado.get("filas_vacias", 0)
        resultado.pop("registros_validos", None)
        return resultado
