# INKubiertos

Sistema de control de inventario y rentabilidad de INKubiertos (Tattoo & food, La Serena, Chile).
Aplicación Streamlit con base de datos en Supabase.

## Objetivo
Registrar entradas, salidas, mermas y ajustes de inventario; calcular el stock por producto y
área desde el historial; y cruzar las ventas exportadas desde FUDO para analizar la rentabilidad.

## Estructura
```
inkubiertos/
├── app.py          # Punto de entrada de Streamlit (enrutador de pantallas)
├── auth/           # Documentación de autenticación
├── components/     # Login y menú lateral
├── config/         # Configuración (.env / secrets de Streamlit)
├── core/           # Reglas puras: RUT, stock, áreas, hora de Chile, límite de login
├── data/           # Capa de datos para la interfaz (permisos, caché, errores en español)
├── db/             # Cliente Supabase, migraciones y verificación de esquema
├── imagenes/       # Imágenes originales (logo y fotografía del local)
├── repositories/   # Acceso a tablas de Supabase
├── scripts/        # Utilidades de línea de comandos
├── services/       # Reglas de negocio (inventario, usuarios, FUDO, importación)
├── static/         # Imágenes optimizadas que sirve Streamlit (generadas)
├── tests/          # Pruebas automatizadas
├── ui/             # Tema visual, formatos y componentes reutilizables
└── views/          # Pantallas de la aplicación
```

## Instalación
1. Crear entorno virtual: `python -m venv .venv`
2. Activarlo:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
3. Instalar dependencias:
   - Solo la app: `pip install -r requirements.txt`
   - App + pruebas: `pip install -r requirements-dev.txt`
4. Copiar `.env.example` a `.env` y completar los valores (o usar `.streamlit/secrets.toml`).
5. Ejecutar: `streamlit run app.py`

## Configuración de Supabase
**Nunca escribir claves en el código.** Usar `.env` o `st.secrets`.

| Variable | Uso |
|---|---|
| `SUPABASE_URL` | URL del proyecto |
| `SUPABASE_KEY` | Clave pública (publishable / anon) |
| `SUPABASE_SERVICE_ROLE_KEY` | Clave secreta. La usa el servidor de Streamlit para conectarse; el navegador nunca la ve |
| `SESSION_TIMEOUT_MINUTES` | Minutos de inactividad antes de cerrar la sesión (por defecto 60) |

Con la clave secreta configurada, ejecutar `db/migrations/005_enable_rls.sql` en el SQL Editor
de Supabase para bloquear el acceso de la clave pública a las tablas.

## Base de datos
El esquema está en `db/migrations/`. Las migraciones **no** se ejecutan automáticamente:
revisarlas, ejecutarlas en Supabase SQL Editor y verificar con
`python scripts/verificar_conexion.py`.

### Tablas principales
- `dim_fecha`, `dim_area`, `dim_usuario` (PK `rut_usuario`), `dim_proveedor` (PK `rut_proveedor`),
  `dim_producto`, `dim_tipo_movimiento`, `dim_evento`
- `hecho_inventario` (sin `costo_total`)
- `hecho_venta_fudo` (independiente)

## Imágenes
Los originales están en `imagenes/`. Si se reemplaza el logo o la fotografía, regenerar las
versiones optimizadas con:
```bash
python scripts/generar_imagenes.py
```

## Pruebas
```bash
pytest -v
```
Las pruebas usan datos ficticios y no escriben en Supabase.

## Notas
- **Stock**: se calcula desde `hecho_inventario` con el `factor_stock` de cada tipo de movimiento.
  Las salidas se validan antes y después de registrarse para evitar stock negativo cuando dos
  personas registran a la vez.
- **Fechas**: todas las marcas de tiempo se guardan en hora de Chile (`America/Santiago`).
- **Permisos**: `Administrador` y `Operario`. La sesión se revalida cada minuto contra la base de
  datos y se cierra tras el tiempo de inactividad configurado.
- **Login**: tras 5 intentos fallidos para un mismo RUT se bloquea durante 5 minutos.
- **FUDO**: los duplicados se detectan por fecha, total, cantidad y producto; si el archivo trae
  número de venta, ticket, comanda u hora, también se usan para distinguir ventas iguales.
