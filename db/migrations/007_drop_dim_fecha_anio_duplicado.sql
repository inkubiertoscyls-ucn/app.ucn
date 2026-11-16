-- 007: Eliminar la columna duplicada dim_fecha."año".
--
-- dim_fecha tenía dos columnas de año: "año" y "anio". Se verificó que en las
-- 4.383 filas (2024-01-01 a 2035-12-31) ambas tenían el mismo valor, igual al
-- año de "fecha". La app solo usa "anio".
--
-- Aplicada en Supabase el 2026-11-16 (junto con 006).
-- Sin CASCADE: si alguna vista dependiera de "año", la sentencia falla y no
-- se borra nada.
-- Ejecutar manualmente en Supabase > SQL Editor.

ALTER TABLE public.dim_fecha DROP COLUMN IF EXISTS "año";

-- Verificación: solo deben aparecer id_fecha, fecha, dia, mes, anio.
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'dim_fecha'
ORDER BY ordinal_position;
