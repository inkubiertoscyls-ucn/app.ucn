-- Migración 003: Alinear hecho_venta_fudo al esquema que usa el importador
-- NO EJECUTAR AUTOMÁTICAMENTE EN BD REMOTA
-- Revisar y ejecutar manualmente en Supabase SQL Editor
--
-- IMPORTANTE:
-- - Mantener hecho_venta_fudo separada de hecho_inventario
-- - No eliminar datos sin verificar. La tabla aparece vacía (0 filas) según comprobación.
-- - Preservar información: si hubiera datos, mapear columnas equivalentes antes de eliminar
-- - Objetivo: unificar con el esquema esperado por services/fudo_import.py

-- Asegurar columnas requeridas por el importador (agregar si no existen)
ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS fecha_venta DATE;

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS origen_archivo VARCHAR(255);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS datos_raw JSONB;

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS total_venta NUMERIC(12,2);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS cantidad_total NUMERIC(10,2);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS producto_identificado VARCHAR(150);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS id_producto_relacionado BIGINT REFERENCES dim_producto(id_producto);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS importado_por VARCHAR(12) REFERENCES dim_usuario(rut_usuario);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS fecha_importacion TIMESTAMP DEFAULT NOW();

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS hash_registro VARCHAR(64);

ALTER TABLE hecho_venta_fudo 
ADD COLUMN IF NOT EXISTS id_evento BIGINT REFERENCES dim_evento(id_evento);

-- Comentarios
COMMENT ON COLUMN hecho_venta_fudo.datos_raw IS 'Datos originales completos del registro importado desde FUDO en formato JSON';
COMMENT ON COLUMN hecho_venta_fudo.hash_registro IS 'Hash SHA256 para detección de duplicados';
COMMENT ON COLUMN hecho_venta_fudo.origen_archivo IS 'Nombre del archivo origen de importación';
COMMENT ON COLUMN hecho_venta_fudo.importado_por IS 'RUT del usuario que realizó la importación';

-- NOTA: Si la tabla tiene datos en columnas antiguas (id_fecha, cantidad_vendida, monto_venta, 
-- origen_venta, fecha_hora_registro, etc.), se recomienda mapear antes de eliminar:
-- Ejemplo (solo si hay datos y se confirma equivalencia):
-- UPDATE hecho_venta_fudo SET fecha_venta = (SELECT fecha FROM dim_fecha WHERE dim_fecha.id_fecha = hecho_venta_fudo.id_fecha) WHERE fecha_venta IS NULL AND id_fecha IS NOT NULL;
-- UPDATE hecho_venta_fudo SET total_venta = monto_venta WHERE total_venta IS NULL AND monto_venta IS NOT NULL;
-- UPDATE hecho_venta_fudo SET cantidad_total = cantidad_vendida WHERE cantidad_total IS NULL AND cantidad_vendida IS NOT NULL;
-- UPDATE hecho_venta_fudo SET origen_archivo = origen_venta WHERE origen_archivo IS NULL AND origen_venta IS NOT NULL;
-- UPDATE hecho_venta_fudo SET fecha_importacion = fecha_hora_registro WHERE fecha_importacion IS NULL AND fecha_hora_registro IS NOT NULL;
--
-- Solo eliminar columnas antiguas tras validar mapeo y respaldo. NO ejecutar aquí sin revisión.
