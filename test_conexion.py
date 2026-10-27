
from db.supabase_client import get_supabase_client
from db.schema_check import SchemaChecker, generate_migration_report

try:
    # Inicializar el cliente
    client = get_supabase_client()
    print("Cliente Supabase inicializado correctamente.")

    # Revisar las tablas y columnas necesarias
    checker = SchemaChecker()
    result = checker.check_all()

    # Mostrar el diagnóstico
    print("\n--- RESULTADO DE LA VERIFICACIÓN ---")
    print(generate_migration_report(result))

except Exception as error:
    print(f"Error durante la verificación: {error}")
