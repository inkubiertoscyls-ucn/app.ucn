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
- `dim_usuario.area_asignada` es texto (nombre de área o `Todas`), no FK
- `hecho_inventario.cantidad` es decimal (`NUMERIC`)
- `dim_fecha` usa solo `anio` (la columna duplicada `año` se eliminó en 007)

## Estado en Supabase (verificado 2026-11-16)
- `001_initial_schema.sql` refleja el esquema real de producción e incluye
  los cambios de 002, 003, 006 y 007.
- 006 (`dim_evento.fecha_evento`) y 007 (eliminar `dim_fecha."año"`): aplicadas.
- 004: no requiere cambios (`area_asignada` ya es texto).

## Seguridad (005_enable_rls.sql)
- La app se conecta con `SUPABASE_SERVICE_ROLE_KEY` (clave secreta) desde el servidor.
- `005_enable_rls.sql` activa RLS en todas las tablas: la clave pública deja de
  tener acceso a los datos. Configurar la clave secreta **antes** de ejecutarla.

## Notas
- Si hay tablas/columnas faltantes, crear migración incremental
- No eliminar tablas o datos existentes
- Respetar nombres y relaciones exactos
