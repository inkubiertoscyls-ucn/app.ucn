# Instrucciones para ejecutar INKubiertos desde VS Code

## Prerrequisitos
- Python 3.10 o superior
- VS Code con la extensión de Python
- Acceso a Supabase (URL y claves)

## Configuración inicial

### 1. Crear el entorno virtual
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias
```bash
pip install -r requirements-dev.txt   # app + pruebas
# o solo la app:
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
Copiar `.env.example` a `.env` (`copy .env.example .env` en Windows) y completar:
```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=sb_publishable_...          # clave pública
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...  # clave secreta (solo servidor)
SESSION_TIMEOUT_MINUTES=60
```

En Streamlit Cloud se usa `.streamlit/secrets.toml`:
```toml
[supabase]
url = "https://tu-proyecto.supabase.co"
key = "sb_publishable_..."
service_role_key = "sb_secret_..."
```

### 4. Verificar conexión y esquema
```bash
python scripts/verificar_conexion.py
```

### 5. Aplicar migraciones (MANUAL)
Las migraciones **no** se ejecutan automáticamente.
1. Abrir Supabase > SQL Editor.
2. Revisar y ejecutar en orden los archivos de `db/migrations/` que falten.
3. **Seguridad:** con `SUPABASE_SERVICE_ROLE_KEY` ya configurada, ejecutar
   `005_enable_rls.sql`. Activa RLS en todas las tablas para que la clave pública no pueda
   leer ni modificar datos.
4. Verificar con `python scripts/verificar_conexion.py`.

### 6. Crear el primer administrador
```bash
python scripts/init_admin.py
```

## Ejecutar la aplicación
```bash
streamlit run app.py
```
La configuración visual y de servidor está en `.streamlit/config.toml` (incluye
`enableStaticServing`, necesario para mostrar el logo y la fotografía desde `static/`).

## Imágenes
Los originales están en `imagenes/`. Tras reemplazar el logo o la fotografía:
```bash
python scripts/generar_imagenes.py
```

## Ejecutar pruebas
```bash
pytest -v                               # todas
pytest tests/test_rut.py -v             # solo RUT
pytest tests/test_inventario_stock.py   # solo inventario
```

## Depuración en VS Code
Crear `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Streamlit: app.py",
      "type": "debugpy",
      "request": "launch",
      "module": "streamlit",
      "args": ["run", "app.py"],
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

## Solución de problemas

### Error de conexión con Supabase
- Revisar URL y claves en `.env`.
- Ejecutar `python scripts/verificar_conexion.py`.
- Si se activó RLS y la app no ve datos, falta `SUPABASE_SERVICE_ROLE_KEY`.

### RUT inválido
- Se aceptan formatos con o sin puntos y guion, y K mayúscula o minúscula.
- `core.utils.normalizar_rut()` y `core.utils.validar_rut()` validan el dígito verificador.

### Stock negativo
- Se rechaza por defecto, también cuando dos personas registran salidas al mismo tiempo.
- `permitir_negativo=True` solo con una regla de negocio autorizada y documentada.

### "Demasiados intentos fallidos"
- Tras 5 contraseñas incorrectas para un RUT, el ingreso se bloquea 5 minutos.

### Archivos .xls de FUDO
- Requieren el paquete `xlrd` (incluido en `requirements.txt`).

## Reglas del proyecto
- **Stock desde historial**: no se guarda el stock resultante.
- **Sin `costo_total`** en `hecho_inventario`.
- **RUT como PK**: sin `id_usuario` ni `id_proveedor` numéricos.
- **FUDO independiente**: no se mezcla con `hecho_inventario`.
- **Sin credenciales en el código**: siempre `.env` o secrets.
- **Migraciones manuales**: nunca automáticas sobre la base remota.
