"""
FUDO Import Service - Flexible importer for FUDO sales exports.

Excel/CSV, configurable column mapping, preview, per-row validation and
duplicate detection. Saves to hecho_venta_fudo (independent from
hecho_inventario).

La importación NO vincula productos automáticamente: la relación con
`dim_producto` se realiza después, de forma manual y explícita desde la
pantalla de FUDO.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from core.exceptions import ValidationError
from db.supabase_client import get_supabase_client
from repositories.base import BaseRepository

logger = logging.getLogger(__name__)

EXTENSIONES_PERMITIDAS = (".csv", ".xlsx", ".xls")

# Campos de destino que la pantalla permite mapear. El evento no se mapea
# porque el archivo de FUDO no contiene un id_evento confiable.
CAMPOS_DESTINO = {
    "fecha_venta": "Fecha de venta",
    "total_venta": "Total de venta",
    "cantidad_total": "Cantidad vendida",
    "producto_identificado": "Producto",
}
CAMPOS_REQUERIDOS = ("fecha_venta", "total_venta")

_CAMPOS_FECHA = ("fecha_venta", "fecha", "Fecha", "fecha de venta", "Fecha Venta")
_CAMPOS_TOTAL = ("total_venta", "total", "monto", "Total", "Monto", "Total Venta")
_CAMPOS_CANTIDAD = ("cantidad_total", "cantidad", "Cantidad", "Cantidad Total")
_CAMPOS_PRODUCTO = (
    "producto_identificado",
    "producto",
    "Producto",
    "item",
    "Item",
    "nombre_producto",
)


def _vacio(valor: Any) -> bool:
    """Considera vacíos None, NaN y cadenas en blanco."""
    if valor is None:
        return True
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(valor, str) and not valor.strip()


def _texto(valor: Any) -> str:
    """Normaliza espacios sin perder mayúsculas ni el contenido original."""
    if _vacio(valor):
        return ""
    return " ".join(str(valor).replace("\u00a0", " ").split())


def _fecha_iso(valor: Any, hoy: Optional[date] = None) -> Tuple[Optional[str], Optional[str]]:
    """Convierte un valor a fecha ISO. Devuelve (fecha, error)."""
    if _vacio(valor):
        return None, "Falta la fecha de venta."

    try:
        if isinstance(valor, datetime):
            parseada = valor
        elif isinstance(valor, date):
            return valor.isoformat(), None
        else:
            parseada = pd.to_datetime(valor, dayfirst=True, errors="raise")
        fecha = pd.Timestamp(parseada).date()
    except Exception:
        return None, "La fecha de venta no es válida."

    referencia = hoy or date.today()
    if fecha > referencia:
        return None, "La fecha de venta no puede ser futura."
    return fecha.isoformat(), None


def _numero(valor: Any) -> Tuple[Optional[float], Optional[str]]:
    """Convierte montos y cantidades aceptando formatos chilenos habituales."""
    if _vacio(valor):
        return None, "El valor está vacío."

    if isinstance(valor, bool):
        return None, "El valor no es numérico."

    if isinstance(valor, (int, float)):
        numero = float(valor)
        if not math.isfinite(numero):
            return None, "El valor no es numérico."
        return numero, None

    texto = str(valor).replace("\u00a0", " ").strip()
    texto = re.sub(r"(?i)(clp|pesos?)", "", texto).replace("$", "")
    texto = texto.replace(" ", "")
    if not texto:
        return None, "El valor está vacío."

    negativo = texto.startswith("-") or (texto.startswith("(") and texto.endswith(")"))
    texto = texto.strip("()")
    if texto.startswith("-"):
        texto = texto[1:]

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes) == 2 and 1 <= len(partes[1]) <= 2:
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "." in texto:
        partes = texto.split(".")
        if (
            len(partes) >= 2
            and partes[0] not in ("0", "")
            and all(len(parte) == 3 for parte in partes[1:])
        ):
            # Formato chileno de miles sin decimales: 1.500 -> 1500.
            texto = texto.replace(".", "")

    try:
        numero = float(texto)
    except (TypeError, ValueError):
        return None, "El valor no es numérico."
    if not math.isfinite(numero):
        return None, "El valor no es numérico."
    return (-numero if negativo else numero), None


def _hash_canonico(
    fecha_venta: Optional[str],
    total_venta: Optional[float],
    cantidad_total: Optional[float],
    producto: str,
) -> str:
    """Hash estable para detectar duplicados exactos entre archivo y BD."""
    partes = [
        fecha_venta or "",
        f"{total_venta:.2f}" if total_venta is not None else "",
        f"{cantidad_total:.4f}" if cantidad_total is not None else "",
        _texto(producto).casefold(),
    ]
    contenido = "|".join(partes)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def _primer_valor(row: Any, claves: Iterable[str]) -> Any:
    for clave in claves:
        try:
            if clave in row:
                valor = row[clave]
                if not _vacio(valor):
                    return valor
        except (TypeError, ValueError):
            continue
    return None


class FudoImportService:
    def __init__(self):
        self.client = get_supabase_client()
        self.ventas_repo = BaseRepository("hecho_venta_fudo")
        self.productos_repo = BaseRepository("dim_producto")
        self.eventos_repo = BaseRepository("dim_evento")

    # ------------------------------------------------------------------
    # Lectura de archivos
    # ------------------------------------------------------------------
    def hojas(self, file_path: str) -> List[str]:
        """Devuelve las hojas disponibles de un archivo Excel o CSV."""
        extension = Path(str(file_path)).suffix.lower()
        if extension == ".csv":
            return ["csv"]
        if extension not in EXTENSIONES_PERMITIDAS:
            raise ValidationError(
                "Formato no soportado. Use un archivo CSV o Excel (.xlsx, .xls)."
            )
        try:
            return list(pd.ExcelFile(file_path).sheet_names)
        except ImportError as exc:
            raise ValidationError(
                "No se pudo leer el archivo .xls. Guárdalo como .xlsx o CSV "
                "y vuelve a intentarlo."
            ) from exc
        except Exception as exc:
            logger.warning("No se pudo leer el archivo Excel: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo leer el archivo Excel. Verifica que el archivo "
                "no esté dañado y vuelve a intentarlo."
            ) from exc

    def _leer_csv(self, file_path: str) -> pd.DataFrame:
        errores: List[str] = []
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            for separador in (None, ";", ","):
                try:
                    return pd.read_csv(
                        file_path,
                        encoding=encoding,
                        sep=separador,
                        engine="python",
                    )
                except Exception as exc:
                    errores.append(type(exc).__name__)
        logger.warning("No se pudo leer CSV (%s)", ", ".join(errores[-3:]))
        raise ValidationError(
            "No se pudo leer el archivo CSV. Verifica que no esté dañado y "
            "que use un formato de texto compatible."
        )

    def leer_hoja(self, file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """Lee una hoja concreta (o el CSV) y devuelve su DataFrame."""
        extension = Path(str(file_path)).suffix.lower()
        if extension == ".csv":
            return self._leer_csv(file_path)
        if extension not in EXTENSIONES_PERMITIDAS:
            raise ValidationError(
                "Formato no soportado. Use un archivo CSV o Excel (.xlsx, .xls)."
            )
        try:
            if extension == ".xls":
                # pandas necesita xlrd para el formato antiguo; si no está,
                # el mensaje debe ser comprensible para el usuario.
                try:
                    import xlrd  # noqa: F401
                except ImportError as exc:
                    raise ValidationError(
                        "El archivo .xls requiere un componente adicional. "
                        "Guárdalo como .xlsx o CSV y vuelve a intentarlo."
                    ) from exc
            return pd.read_excel(file_path, sheet_name=sheet_name if sheet_name else 0)
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning("No se pudo leer la hoja del archivo: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo leer la hoja del archivo. Verifica que el archivo "
                "no esté dañado y vuelve a intentarlo."
            ) from exc

    def leer_archivo(self, file_path: str) -> Tuple[pd.DataFrame, str]:
        """Lee el archivo y devuelve (DataFrame, hoja o tipo)."""
        extension = Path(str(file_path)).suffix.lower()
        if extension == ".csv":
            return self._leer_csv(file_path), "csv"
        hojas = self.hojas(file_path)
        hoja = hojas[0] if hojas else 0
        return self.leer_hoja(file_path, hoja), hoja

    # ------------------------------------------------------------------
    # Inspección y vista previa
    # ------------------------------------------------------------------
    def inspeccionar_archivo(self, file_path: str) -> Dict:
        """Inspecciona hojas, columnas y una muestra de cada hoja."""
        try:
            resultado: Dict[str, Any] = {
                "tipo": None,
                "hojas": [],
                "columnas_por_hoja": {},
                "preview": {},
            }
            extension = Path(str(file_path)).suffix.lower()
            if extension == ".csv":
                resultado["tipo"] = "csv"
                df = self._leer_csv(file_path)
                resultado["hojas"] = ["csv"]
                resultado["columnas_por_hoja"] = {"csv": list(df.columns)}
                resultado["preview"]["csv"] = df.head(10).to_dict("records")
            else:
                resultado["tipo"] = "excel"
                hojas = self.hojas(file_path)
                resultado["hojas"] = hojas
                for hoja in hojas:
                    df = self.leer_hoja(file_path, hoja)
                    resultado["columnas_por_hoja"][hoja] = list(df.columns)
                    resultado["preview"][hoja] = df.head(10).to_dict("records")
            return resultado
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning("Error al inspeccionar el archivo: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo inspeccionar el archivo. Verifica el formato y "
                "vuelve a intentarlo."
            ) from exc

    def crear_mapeo_columnas(
        self,
        columnas_origen: List[str],
        mapeo_config: Dict[str, str],
    ) -> Dict:
        """Filtra un mapeo configurable a las columnas realmente presentes."""
        mapeo = {}
        for origen, destino in (mapeo_config or {}).items():
            if origen in columnas_origen and destino in CAMPOS_DESTINO:
                mapeo[origen] = destino
        return mapeo

    def normalizar_mapeo(self, mapeo_config: Dict[str, str]) -> Dict[str, str]:
        """Valida que el mapeo cubra los campos obligatorios sin ambigüedad."""
        mapeo: Dict[str, str] = {}
        destinos: Dict[str, str] = {}

        for origen, destino in (mapeo_config or {}).items():
            origen_texto = str(origen or "").strip()
            destino_texto = str(destino or "").strip()
            if not origen_texto or not destino_texto:
                continue
            if destino_texto not in CAMPOS_DESTINO:
                raise ValidationError(
                    "El mapeo contiene un campo de destino no reconocido."
                )
            if destino_texto in destinos:
                raise ValidationError(
                    "Dos columnas del archivo no pueden mapearse al mismo campo: "
                    f"{CAMPOS_DESTINO[destino_texto]}."
                )
            mapeo[origen_texto] = destino_texto
            destinos[destino_texto] = origen_texto

        for campo in CAMPOS_REQUERIDOS:
            if campo not in destinos:
                raise ValidationError(
                    "Falta mapear una columna obligatoria: "
                    f"{CAMPOS_DESTINO[campo]}."
                )
        return mapeo

    def previsualizar_importacion(
        self,
        file_path: str,
        sheet_name: str = None,
        mapeo_columnas: Dict = None,
    ) -> Dict:
        """Vista previa de los datos con el mapeo aplicado."""
        try:
            df = self.leer_hoja(file_path, sheet_name)
            if mapeo_columnas:
                mapeo = self.normalizar_mapeo(mapeo_columnas)
                df_mapeado = self._renombrar(df, mapeo)
            else:
                df_mapeado = df.copy()

            return {
                "total_filas": len(df),
                "columnas_origen": list(df.columns),
                "columnas_mapeadas": list(df_mapeado.columns),
                "datos_preview": df_mapeado.head(20).to_dict("records"),
                "validacion_preliminar": self._validar_preliminar(df_mapeado),
            }
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning("Error en previsualización: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo generar la vista previa. Revisa el mapeo de "
                "columnas y vuelve a intentarlo."
            ) from exc

    def _renombrar(self, df: pd.DataFrame, mapeo: Dict[str, str]) -> pd.DataFrame:
        """Renombra columnas y evita destinos duplicados."""
        columnas = [mapeo.get(str(col), str(col)) for col in df.columns]
        repetidas = sorted({col for col in columnas if columnas.count(col) > 1})
        if repetidas:
            raise ValidationError(
                "El mapeo genera columnas duplicadas: "
                + ", ".join(str(col) for col in repetidas)
                + ". Revisa la selección."
            )
        renombrado = df.copy()
        renombrado.columns = columnas
        return renombrado

    def _validar_preliminar(self, df: pd.DataFrame) -> Dict:
        """Comprobaciones generales de columnas antes de validar cada fila."""
        advertencias: List[str] = []
        if "fecha_venta" not in df.columns and "fecha" not in df.columns:
            advertencias.append("No se detectó una columna de fecha de venta.")
        if not {"total_venta", "total", "monto"} & set(df.columns):
            advertencias.append("No se detectó una columna de total o monto.")
        if not {"cantidad_total", "cantidad"} & set(df.columns):
            advertencias.append(
                "No se detectó una columna de cantidad. El costo estimado no "
                "podrá calcularse para estas ventas."
            )
        return {
            "errores": [],
            "advertencias": advertencias,
            "filas_con_datos": len(df.dropna(how="all")),
        }

    # ------------------------------------------------------------------
    # Validación por registro
    # ------------------------------------------------------------------
    def _evaluar_dataframe(
        self,
        df: pd.DataFrame,
        mapeo: Dict[str, str],
        hashes_existentes: Optional[Iterable[str]] = None,
        *,
        incluir_registros: bool = False,
    ) -> Dict[str, Any]:
        """Valida cada fila y clasifica válidos, errores y duplicados."""
        mapeo = self.normalizar_mapeo(mapeo)
        existentes = {
            str(hash_registro)
            for hash_registro in (hashes_existentes or [])
            if hash_registro
        }
        df_mapeado = self._renombrar(df, mapeo)
        hoy = date.today()

        filas: List[Dict[str, Any]] = []
        errores: List[Dict[str, Any]] = []
        advertencias: List[Dict[str, Any]] = []
        registros_validos: List[Dict[str, Any]] = []
        vistos: Dict[str, int] = {}

        total_filas = len(df)
        filas_vacias = 0
        validos = 0
        con_error = 0
        duplicados = 0
        advertencias_total = 0

        for posicion, (_indice, fila_original) in enumerate(df.iterrows(), start=1):
            if all(_vacio(valor) for valor in fila_original.to_dict().values()):
                filas_vacias += 1
                continue

            fila = df_mapeado.iloc[posicion - 1]
            errores_fila: List[str] = []
            advertencias_fila: List[str] = []

            fecha_iso, error_fecha = _fecha_iso(fila.get("fecha_venta"), hoy)
            if error_fecha:
                errores_fila.append(error_fecha)

            total, error_total = _numero(fila.get("total_venta"))
            if error_total:
                errores_fila.append(f"Total de venta: {error_total}")
            elif total is not None and total < 0:
                errores_fila.append("El total de venta no puede ser negativo.")

            cantidad: Optional[float] = None
            if "cantidad_total" in mapeo.values():
                cantidad, error_cantidad = _numero(fila.get("cantidad_total"))
                if error_cantidad:
                    advertencias_fila.append(
                        "Cantidad vendida no informada o inválida; el costo "
                        "estimado no se calculará para este registro."
                    )
                elif cantidad is not None and cantidad < 0:
                    errores_fila.append("La cantidad vendida no puede ser negativa.")
                elif cantidad == 0:
                    advertencias_fila.append(
                        "La cantidad vendida es cero; el costo estimado no se "
                        "calculará para este registro."
                    )

            producto = _texto(fila.get("producto_identificado"))
            if not producto:
                errores_fila.append("Falta el nombre del producto.")
            elif len(producto) > 150:
                errores_fila.append(
                    "El nombre del producto supera los 150 caracteres."
                )

            datos_raw = json.loads(
                json.dumps(
                    {str(clave): valor for clave, valor in fila_original.to_dict().items()},
                    default=str,
                )
            )

            numero_registro = posicion

            if errores_fila:
                con_error += 1
                detalle = {
                    "registro": numero_registro,
                    "producto": producto or "—",
                    "fecha": fecha_iso or "—",
                    "detalle": " ".join(errores_fila),
                }
                errores.append(detalle)
                filas.append(
                    {
                        "registro": numero_registro,
                        "estado": "error",
                        "producto": producto,
                        "fecha": fecha_iso,
                        "total": total,
                        "cantidad": cantidad,
                        "detalle": detalle["detalle"],
                    }
                )
                continue

            hash_registro = _hash_canonico(fecha_iso, total, cantidad, producto)

            if hash_registro in existentes:
                duplicados += 1
                detalle = {
                    "registro": numero_registro,
                    "producto": producto,
                    "fecha": fecha_iso or "—",
                    "detalle": "Ya existe una venta con los mismos datos en la base.",
                }
                errores.append(detalle)
                filas.append(
                    {
                        "registro": numero_registro,
                        "estado": "duplicado",
                        "producto": producto,
                        "fecha": fecha_iso,
                        "total": total,
                        "cantidad": cantidad,
                        "detalle": detalle["detalle"],
                    }
                )
                continue

            if hash_registro in vistos:
                duplicados += 1
                detalle = {
                    "registro": numero_registro,
                    "producto": producto,
                    "fecha": fecha_iso or "—",
                    "detalle": (
                        "Repite un registro del mismo archivo "
                        f"(registro {vistos[hash_registro]})."
                    ),
                }
                errores.append(detalle)
                filas.append(
                    {
                        "registro": numero_registro,
                        "estado": "duplicado",
                        "producto": producto,
                        "fecha": fecha_iso,
                        "total": total,
                        "cantidad": cantidad,
                        "detalle": detalle["detalle"],
                    }
                )
                continue

            vistos[hash_registro] = numero_registro
            validos += 1
            if advertencias_fila:
                advertencias_total += 1
                advertencias.append(
                    {
                        "registro": numero_registro,
                        "producto": producto,
                        "detalle": " ".join(advertencias_fila),
                    }
                )

            filas.append(
                {
                    "registro": numero_registro,
                    "estado": "valido",
                    "producto": producto,
                    "fecha": fecha_iso,
                    "total": total,
                    "cantidad": cantidad,
                    "detalle": " ".join(advertencias_fila),
                }
            )

            if incluir_registros:
                registros_validos.append(
                    {
                        "hash_registro": hash_registro,
                        "datos": {
                            "fecha_venta": fecha_iso,
                            "total_venta": round(total, 2) if total is not None else None,
                            "cantidad_total": (
                                round(cantidad, 4) if cantidad is not None else None
                            ),
                            "producto_identificado": producto,
                        },
                        "datos_raw": datos_raw,
                    }
                )

        advertencias_generales: List[str] = []
        if "cantidad_total" not in mapeo.values():
            advertencias_generales.append(
                "No se mapeó la cantidad vendida. Las ventas se importarán, "
                "pero no podrán incluirse en el costo ni en la utilidad estimada."
            )

        resultado: Dict[str, Any] = {
            "total_filas": total_filas,
            "filas_vacias": filas_vacias,
            "total_consideradas": total_filas - filas_vacias,
            "validos": validos,
            "con_error": con_error,
            "duplicados": duplicados,
            "advertencias": advertencias_total,
            "importables": validos,
            "filas": filas,
            "errores": errores,
            "detalle_advertencias": advertencias,
            "advertencias_generales": advertencias_generales,
            "columnas_origen": [str(col) for col in df.columns],
            "mapeo": dict(mapeo),
        }
        if incluir_registros:
            resultado["registros_validos"] = registros_validos
        return resultado

    def analizar_dataframe(
        self,
        df: pd.DataFrame,
        mapeo_columnas: Dict,
        hashes_existentes: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Analiza el DataFrame sin escribir nada en la base de datos."""
        try:
            return self._evaluar_dataframe(
                df,
                mapeo_columnas,
                hashes_existentes,
                incluir_registros=False,
            )
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning("No se pudo validar el archivo: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo validar el archivo. Revisa su contenido y vuelve "
                "a intentarlo."
            ) from exc

    def detectar_duplicados(self, df: pd.DataFrame) -> Dict:
        """Detecta duplicados internos usando el hash canónico de cada fila."""
        try:
            hashes = [
                self._crear_hash_registro(fila)
                for _, fila in df.iterrows()
                if not all(_vacio(valor) for valor in fila.to_dict().values())
            ]
            repetidos = sorted(
                {
                    hash_registro
                    for hash_registro in hashes
                    if hashes.count(hash_registro) > 1
                }
            )
            return {
                "hay_duplicados": bool(repetidos),
                "cantidad_duplicados": sum(
                    1 for hash_registro in hashes if hash_registro in repetidos
                ),
                "hashes_duplicados": repetidos,
            }
        except Exception as exc:
            logger.warning(
                "No se pudieron detectar duplicados: %s", type(exc).__name__
            )
            return {
                "hay_duplicados": False,
                "error": "No se pudieron detectar duplicados.",
            }

    def _crear_hash_registro(self, row) -> str:
        """Hash compatible con la detección antigua y con el formato nuevo."""
        fecha_valor = _primer_valor(row, _CAMPOS_FECHA)
        fecha_iso, _ = _fecha_iso(fecha_valor)
        total, _ = _numero(_primer_valor(row, _CAMPOS_TOTAL))
        cantidad, _ = _numero(_primer_valor(row, _CAMPOS_CANTIDAD))
        producto = _texto(_primer_valor(row, _CAMPOS_PRODUCTO))
        return _hash_canonico(fecha_iso, total, cantidad, producto)

    # ------------------------------------------------------------------
    # Importación
    # ------------------------------------------------------------------
    def importar_dataframe(
        self,
        df: pd.DataFrame,
        mapeo_columnas: Dict,
        importado_por: Optional[str] = None,
        origen_archivo: Optional[str] = None,
        hashes_existentes: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Importa únicamente registros válidos y no duplicados.

        No vincula productos ni eventos automáticamente. Los registros
        duplicados se informan por separado y no se escriben.
        """
        try:
            analisis = self._evaluar_dataframe(
                df,
                mapeo_columnas,
                hashes_existentes,
                incluir_registros=True,
            )
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning("No se pudo preparar la importación: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo preparar la importación. Vuelve a intentarlo."
            ) from exc

        resultados: Dict[str, Any] = {
            "importados": 0,
            "rechazados": analisis["con_error"],
            "duplicados": analisis["duplicados"],
            "total_filas": analisis["total_filas"],
            "filas_vacias": analisis["filas_vacias"],
            "advertencias": analisis["advertencias"],
            "errores": list(analisis["errores"]),
            "detalle_advertencias": list(analisis["detalle_advertencias"]),
            "advertencias_generales": list(analisis["advertencias_generales"]),
        }

        origen = origen_archivo or "archivo FUDO"
        ahora = datetime.now().isoformat()

        for registro in analisis.get("registros_validos", []):
            datos = registro["datos"]
            fila = {
                "fecha_venta": datos.get("fecha_venta"),
                "id_evento": None,
                "origen_archivo": origen,
                "datos_raw": registro.get("datos_raw"),
                "total_venta": datos.get("total_venta"),
                "cantidad_total": datos.get("cantidad_total"),
                "producto_identificado": datos.get("producto_identificado"),
                # La vinculación se hace después, siempre manual.
                "id_producto_relacionado": None,
                "hash_registro": registro.get("hash_registro"),
            }
            if importado_por:
                fila["importado_por"] = str(importado_por)
            fila["fecha_importacion"] = ahora

            try:
                self.ventas_repo.create(fila)
                resultados["importados"] += 1
            except Exception as exc:
                resultados["rechazados"] += 1
                resultados["errores"].append(
                    {
                        "registro": "—",
                        "producto": datos.get("producto_identificado") or "—",
                        "fecha": datos.get("fecha_venta") or "—",
                        "detalle": (
                            "No se pudo guardar la venta. Revisa la conexión "
                            "e intenta nuevamente."
                        ),
                    }
                )
                logger.error("Error al importar una venta FUDO: %s", type(exc).__name__)

        return resultados

    def importar_ventas(
        self,
        file_path: str,
        sheet_name: str = None,
        mapeo_columnas: Dict = None,
        importado_por: str = None,
        origen_archivo: str = None,
    ) -> Dict:
        """Importa un archivo completo (compatibilidad con la versión anterior)."""
        try:
            df = self.leer_hoja(file_path, sheet_name)
            if mapeo_columnas:
                mapeo = self.normalizar_mapeo(mapeo_columnas)
            else:
                # Modo heredado: columnas ya normalizadas.
                mapeo = {col: col for col in df.columns if col in CAMPOS_DESTINO}
                for campo in CAMPOS_REQUERIDOS:
                    if campo not in mapeo:
                        raise ValidationError(
                            "Falta una columna obligatoria para importar: "
                            f"{CAMPOS_DESTINO[campo]}."
                        )
            if origen_archivo is None:
                origen_archivo = Path(str(file_path)).name
            return self.importar_dataframe(
                df,
                mapeo,
                importado_por=importado_por,
                origen_archivo=origen_archivo,
            )
        except ValidationError:
            raise
        except Exception as exc:
            logger.warning("Error en importación: %s", type(exc).__name__)
            raise ValidationError(
                "No se pudo completar la importación. Vuelve a intentarlo."
            ) from exc

    def _procesar_fila(
        self,
        row,
        origen_archivo: str,
        importado_por: str = None,
    ) -> Optional[Dict]:
        """Procesa una fila ya normalizada. No vincula productos automáticamente."""
        try:
            registro: Dict[str, Any] = {
                "origen_archivo": origen_archivo,
                "datos_raw": json.loads(
                    json.dumps(row.to_dict(), default=str)
                ),
                "fecha_importacion": datetime.now().isoformat(),
            }
            if importado_por:
                registro["importado_por"] = importado_por

            fecha_iso, _ = _fecha_iso(_primer_valor(row, _CAMPOS_FECHA))
            if fecha_iso:
                registro["fecha_venta"] = fecha_iso

            total, _ = _numero(_primer_valor(row, _CAMPOS_TOTAL))
            if total is not None and total >= 0:
                registro["total_venta"] = round(total, 2)

            cantidad, _ = _numero(_primer_valor(row, _CAMPOS_CANTIDAD))
            if cantidad is not None and cantidad >= 0:
                registro["cantidad_total"] = round(cantidad, 4)

            producto = _texto(_primer_valor(row, _CAMPOS_PRODUCTO))
            if producto:
                registro["producto_identificado"] = producto

            registro["hash_registro"] = self._crear_hash_registro(row)

            if not registro.get("fecha_venta") and not registro.get("total_venta"):
                return None
            return registro
        except Exception:
            return None

    def listar_importaciones(self, limit: int = 50) -> List[Dict]:
        """Lista importaciones recientes sin exponer `datos_raw`."""
        try:
            response = (
                self.client.table("hecho_venta_fudo")
                .select(
                    "id_venta_fudo, fecha_venta, id_evento, origen_archivo, "
                    "total_venta, cantidad_total, producto_identificado, "
                    "id_producto_relacionado, importado_por, fecha_importacion"
                )
                .order("fecha_importacion", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception:
            return []
