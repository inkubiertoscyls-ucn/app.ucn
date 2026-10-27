
"""Verifica el esquema real de Supabase sin modificar la base de datos."""

import logging
from typing import Any

from db.supabase_client import get_supabase_client
from core.exceptions import SupabaseConnectionError

logger = logging.getLogger(__name__)

EXPECTED_SCHEMA = {
    "dim_fecha": [
        "id_fecha", "fecha", "dia", "mes", "anio"
    ],
    "dim_area": [
        "id_area", "nombre_area", "descripcion_area", "activo"
    ],
    "dim_usuario": [
        "rut_usuario", "nombre_usuario", "rol", "area_asignada",
        "password_hash", "activo", "fecha_creacion"
    ],
    "dim_proveedor": [
        "rut_proveedor", "nombre_proveedor", "contacto_proveedor",
        "tipo_proveedor", "activo"
    ],
    "dim_producto": [
        "id_producto", "nombre_producto", "categoria",
        "unidad_medida", "costo_base", "stock_minimo",
        "stock_maximo", "activo"
    ],
    "dim_tipo_movimiento": [
        "id_tipo_movimiento", "tipo_movimiento",
        "factor_stock", "descripcion", "activo"
    ],
    "dim_evento": [
        "id_evento", "nombre_evento", "nombre_artista",
        "tipo_evento", "costo_artista", "activo"
    ],
    "hecho_inventario": [
        "id_hecho_inventario", "id_fecha", "id_producto",
        "id_area", "id_tipo_movimiento", "rut_usuario",
        "rut_proveedor", "id_evento", "cantidad",
        "costo_unitario", "observacion", "fecha_hora_registro"
    ],
    "hecho_venta_fudo": [
        "id_venta_fudo", "fecha_venta", "id_evento", "origen_archivo",
        "datos_raw", "total_venta", "cantidad_total",
        "producto_identificado", "id_producto_relacionado",
        "importado_por", "fecha_importacion", "hash_registro"
    ],
}

FORBIDDEN_COLUMNS = {
    "dim_usuario": ["id_usuario"],
    "dim_proveedor": ["id_proveedor"],
    "dim_producto": ["area_habitual"],
    "hecho_inventario": ["costo_total"],
}


def error_text(error: Exception) -> str:
    """Devuelve el detalle del error para el informe."""
    code = getattr(error, "code", None)
    prefix = f"Código {code}: " if code else ""
    return prefix + str(error)


def is_missing_table(error: Exception) -> bool:
    """Solo clasifica como inexistente un error explícito de tabla."""
    message = error_text(error).lower()

    # Un error de caché o permisos no prueba que falte la tabla.
    if "schema cache" in message:
        return False

    return (
        "42p01" in message
        or "undefinedtable" in message
        or "relation" in message and "does not exist" in message
    )


def is_missing_column(error: Exception, column: str) -> bool:
    """Reconoce errores explícitos de columna inexistente."""
    message = error_text(error).lower()

    # PostgREST puede informar de una caché desactualizada.
    if "schema cache" in message:
        return False

    return (
        "undefinedcolumn" in message
        or "42703" in message
        or (
            column.lower() in message
            and "column" in message
            and (
                "does not exist" in message
                or "undefined" in message
            )
        )
    )


class SchemaChecker:
    def __init__(self):
        self.client = get_supabase_client()

    def check_all(self) -> dict[str, Any]:
        result = {
            "ok": True,
            "missing_tables": [],
            "missing_columns": {},
            "forbidden_found": {},
            "errors_by_table": {},
            "verification_errors": {},
            "recommendations": [],
        }

        for table, expected_columns in EXPECTED_SCHEMA.items():
            # Primero comprobar si se puede consultar la tabla.
            try:
                self.client.table(table).select("*").limit(1).execute()
            except Exception as error:
                message = error_text(error)
                result["ok"] = False

                if is_missing_table(error):
                    result["missing_tables"].append(table)
                else:
                    result["errors_by_table"][table] = message

                continue

            # Comprobar las columnas requeridas.
            for column in expected_columns:
                try:
                    (
                        self.client.table(table)
                        .select(column)
                        .limit(1)
                        .execute()
                    )
                except Exception as error:
                    result["ok"] = False

                    if is_missing_column(error, column):
                        result["missing_columns"].setdefault(
                            table, []
                        ).append(column)
                    else:
                        result["verification_errors"][
                            f"{table}.{column}"
                        ] = error_text(error)

            # Comprobar columnas que no deberían existir.
            for column in FORBIDDEN_COLUMNS.get(table, []):
                try:
                    (
                        self.client.table(table)
                        .select(column)
                        .limit(1)
                        .execute()
                    )
                except Exception as error:
                    if is_missing_column(error, column):
                        # La columna no existe según el error explícito.
                        continue

                    # No asumir que está ausente si el error es ambiguo.
                    result["verification_errors"][
                        f"{table}.{column}"
                    ] = error_text(error)
                    result["ok"] = False
                else:
                    result["forbidden_found"].setdefault(
                        table, []
                    ).append(column)
                    result["ok"] = False

        if result["missing_tables"]:
            result["recommendations"].append(
                "Verificar las tablas faltantes antes de preparar una "
                "migración SQL. No ejecutar migraciones automáticamente."
            )

        if result["missing_columns"]:
            result["recommendations"].append(
                "Revisar las columnas faltantes y compararlas con el "
                "esquema esperado."
            )

        if result["forbidden_found"]:
            result["recommendations"].append(
                "Confirmar las columnas prohibidas antes de preparar "
                "cualquier modificación."
            )

        if result["errors_by_table"] or result["verification_errors"]:
            result["recommendations"].append(
                "Revisar los errores de acceso o de esquema. Un error "
                "de permisos o caché no demuestra que falte una tabla."
            )

        return result


def generate_migration_report(check_result: dict[str, Any]) -> str:
    report = [
        "# REPORTE DE VERIFICACIÓN DE ESQUEMA",
        "",
        f"Estado: {'OK' if check_result.get('ok') else 'REQUIERE ATENCIÓN'}",
        "",
    ]

    sections = [
        ("Tablas que no existen según el error recibido",
         check_result.get("missing_tables", [])),
        ("Columnas faltantes",
         check_result.get("missing_columns", {})),
        ("Columnas prohibidas accesibles",
         check_result.get("forbidden_found", {})),
        ("Errores al acceder a tablas",
         check_result.get("errors_by_table", {})),
        ("Errores de verificación de columnas",
         check_result.get("verification_errors", {})),
    ]

    for title, values in sections:
        if not values:
            continue

        report.extend([f"## {title}", ""])

        if isinstance(values, dict):
            for name, detail in values.items():
                if isinstance(detail, list):
                    report.append(f"- {name}: {', '.join(detail)}")
                else:
                    report.append(f"- {name}: {detail}")
        else:
            for value in values:
                report.append(f"- {value}")

        report.append("")

    recommendations = check_result.get("recommendations", [])
    if recommendations:
        report.extend(["## Recomendaciones", ""])
        report.extend(f"- {item}" for item in recommendations)
        report.append("")

    report.append(
        "Nota: este verificador no modifica la base de datos remota."
    )
    return "\n".join(report)
