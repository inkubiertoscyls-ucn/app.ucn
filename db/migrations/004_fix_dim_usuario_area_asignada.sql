-- Migración 004: Ajustar area_asignada en dim_usuario para permitir 'Todas' si es necesario
-- NO EJECUTAR AUTOMÁTICAMENTE EN BD REMOTA
-- Revisar y ejecutar manualmente en Supabase SQL Editor

-- NOTA: En el esquema actual (001_initial_schema.sql) area_asignada es BIGINT REFERENCES dim_area(id_area).
-- Si la restricción real en Supabase es NOT NULL o es diferente, puede requerir ajuste.
-- 
-- OPCIÓN 1: Si area_asignada debe permitir texto 'Todas' para administradores
-- ALTER TABLE dim_usuario ALTER COLUMN area_asignada TYPE VARCHAR(50);
-- (Cuidado: esto cambia el tipo si hay FK. Verificar relaciones)
--
-- OPCIÓN 2: Si se mantiene FK a dim_area, crear área 'Todas' e insertar su id_area
-- INSERT INTO dim_area (nombre_area, descripcion_area, activo) 
-- VALUES ('Todas', 'Área para administradores con acceso global', true)
-- ON CONFLICT DO NOTHING;
-- Luego actualizar: UPDATE dim_usuario SET area_asignada = (SELECT id_area FROM dim_area WHERE nombre_area='Todas' LIMIT 1) WHERE area_asignada IS NULL;

-- RECOMENDACIÓN: Verificar estructura real en Supabase antes de aplicar.
-- El código ahora envía area_asignada = 'Todas'. Si el tipo es BIGINT con FK, 
-- esta migración debe ajustarse según el esquema real.
