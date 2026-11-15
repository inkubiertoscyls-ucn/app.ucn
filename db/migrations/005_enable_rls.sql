-- 005: Activar Row Level Security (RLS) en todas las tablas del esquema public.
--
-- Por qué: sin RLS, cualquiera que obtenga la clave pública (publishable/anon)
-- puede leer y modificar todas las tablas por la API REST de Supabase,
-- incluidos los hashes de contraseñas de dim_usuario.
--
-- La aplicación se conecta desde el servidor de Streamlit con la clave
-- secreta (SUPABASE_SERVICE_ROLE_KEY), que ignora RLS. Por eso basta con
-- activar RLS sin crear políticas: la app sigue funcionando y la clave
-- pública queda sin acceso a los datos.
--
-- ANTES DE EJECUTAR: confirmar que SUPABASE_SERVICE_ROLE_KEY está configurada
-- en el .env (o en los secrets de Streamlit) del servidor donde corre la app.
-- Ejecutar manualmente en Supabase > SQL Editor.

DO $$
DECLARE
    tabla RECORD;
BEGIN
    FOR tabla IN
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tabla.tablename);
    END LOOP;
END $$;

-- Verificación: todas las filas deben mostrar rowsecurity = true.
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
