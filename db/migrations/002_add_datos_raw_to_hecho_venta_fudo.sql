-- Migración 002: Asegurar columna datos_raw en hecho_venta_fudo
-- NO EJECUTAR AUTOMÁTICAMENTE EN BD REMOTA
-- Revisar y ejecutar manualmente en Supabase SQL Editor

-- Agregar columna datos_raw si no existe (JSONB para conservar datos originales)
ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS datos_raw JSONB;

-- Comentario para documentación
COMMENT ON COLUMN hecho_venta_fudo.datos_raw IS 'Datos originales completos del registro importado desde FUDO en formato JSON';
