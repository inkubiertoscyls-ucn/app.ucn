# Migraciones de Base de Datos

**IMPORTANTE:** NO ejecutar automáticamente. Estas migraciones son para referencia y aplicación manual.

## Proceso
1. Revisar el esquema actual en Supabase
2. Comparar con `001_initial_schema.sql`
3. Ejecutar migraciones necesarias en Supabase SQL Editor
4. Verificar con `db/schema_check.py`

## Requisitos del esquema
- `dim_usuario.rut_usuario` = PRIMARY KEY (NO `id_usuario`)
- `dim_proveedor.rut_proveedor` = PRIMARY KEY (NO `id_proveedor`)
- `dim_producto` SIN columna `area_habitual`
- `hecho_inventario` SIN columna `costo_total`
- `hecho_venta_fudo` tabla independiente

## Notas
- Si hay tablas/columnas faltantes, crear migración incremental
- No eliminar tablas o datos existentes
- Respetar nombres y relaciones exactos
