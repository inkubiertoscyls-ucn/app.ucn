
from db.supabase_client import get_supabase_client

client = get_supabase_client()

tablas = [
    "dim_fecha",
    "dim_area",
    "dim_usuario",
    "dim_proveedor",
    "dim_producto",
    "dim_tipo_movimiento",
    "dim_evento",
    "hecho_inventario",
    "hecho_venta_fudo",
]

print("\n--- COMPROBACIÓN DE TABLAS EN SUPABASE ---")

for tabla in tablas:
    try:
        respuesta = (
            client.table(tabla)
            .select("*")
            .limit(1)
            .execute()
        )
        print(f"OK: {tabla} | Filas devueltas: {len(respuesta.data)}")

    except Exception as error:
        print(f"ERROR: {tabla}")
        print(f"  Tipo: {type(error).__name__}")
        print(f"  Detalle: {error}")
