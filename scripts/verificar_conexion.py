#!/usr/bin/env python
"""Verifica la conexión con Supabase y que el esquema tenga lo esperado.

Uso (desde la raíz del proyecto):
    python scripts/verificar_conexion.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.schema_check import SchemaChecker, generate_migration_report  # noqa: E402
from db.supabase_client import SupabaseClient  # noqa: E402

TABLAS = (
    "dim_fecha",
    "dim_area",
    "dim_usuario",
    "dim_proveedor",
    "dim_producto",
    "dim_tipo_movimiento",
    "dim_evento",
    "hecho_inventario",
    "hecho_venta_fudo",
)


def main() -> int:
    try:
        cliente = SupabaseClient()
    except Exception as error:
        print(f"No se pudo inicializar el cliente: {error}")
        return 1

    if not cliente.health_check():
        print("Supabase no responde. Revisa SUPABASE_URL y las claves del .env.")
        return 1
    print("Conexión con Supabase: OK\n")

    print("--- Tablas ---")
    for tabla in TABLAS:
        try:
            filas = cliente.table(tabla).select("*").limit(1).execute().data
            print(f"OK    {tabla} ({len(filas)} fila de muestra)")
        except Exception as error:
            print(f"ERROR {tabla}: {type(error).__name__}")

    print("\n--- Esquema ---")
    print(generate_migration_report(SchemaChecker().check_all()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
