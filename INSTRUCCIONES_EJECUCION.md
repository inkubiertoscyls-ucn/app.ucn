# Instrucciones para ejecutar el backend desde VS Code

## Prerequisitos
- Python 3.10 o superior
- VS Code con extensión Python
- Acceso a Supabase (URL y keys)
- Git (opcional)

## Configuración inicial

### 1. Crear entorno virtual
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Windows (CMD)
python -m venv .venv
.\.venv\Scripts\activate.bat

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
Copiar `.env.example` a `.env`:
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Editar `.env` con credenciales reales:
```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu-anon-key
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key
```

**SI USAS STREAMLIT:** También puedes usar `.streamlit/secrets.toml`:
```toml
[supabase]
url = "https://tu-proyecto.supabase.co"
key = "tu-anon-key"
service_role_key = "tu-service-role-key"
```

### 4. Verificar conexión y esquema
```python
# En terminal de Python o script
from db.supabase_client import get_supabase_client
from db.schema_check import SchemaChecker, generate_migration_report

client = get_supabase_client()
checker = SchemaChecker()
result = checker.check_all()
print(generate_migration_report(result))
```

### 5. Aplicar migraciones (MANUAL)
**NO se ejecutan automáticamente.**
1. Abrir Supabase SQL Editor
2. Copiar contenido de `db/migrations/001_initial_schema.sql`
3. Revisar y ejecutar manualmente
4. Verificar esquema con el checker

## Ejecutar pruebas
```bash
# Todas las pruebas
pytest tests/ -v

# Con más detalle
pytest tests/ -v --tb=short

# Solo pruebas de RUT
pytest tests/test_rut.py -v

# Solo inventario
pytest tests/test_inventario_stock.py -v
```

**Nota:** Las pruebas que requieren acceso real a Supabase o archivos FUDO se marcarán como `SKIPPED`.

## Uso desde VS Code

### Debugging
Crear `launch.json` en `.vscode/`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

### Integración con Streamlit
```python
import streamlit as st
from config.settings import get_settings
from services.inventario import InventarioService

# Cargar con secrets de Streamlit
settings = get_settings(use_streamlit=True)
inventario = InventarioService()

# Usar servicios
```

## Estructura de uso
```python
# Productos
from services.productos import ProductosService
prod_service = ProductosService()
productos = prod_service.listar_productos()

# Inventario
from services.inventario import InventarioService
inv_service = InventarioService()
stock = inv_service.calcular_stock_actual(id_producto=1, id_area=1)

# Movimientos
data_entrada = {
    "id_producto": 1,
    "id_area": 1,
    "id_tipo_movimiento": 1,  # Entrada
    "rut_usuario": "12345678-9",
    "cantidad": 10,
    "costo_unitario": 1000,
    "rut_proveedor": "98765432-1"
}
inv_service.registrar_entrada(data_entrada)

# FUDO Import
from services.fudo_import import FudoImportService
fudo = FudoImportService()
info = fudo.inspeccionar_archivo("ventas_fudo.xlsx")
# Configurar mapeo y previsualizar
```

## Troubleshooting

### Error de conexión Supabase
- Verificar URL y keys en `.env`
- Comprobar que las tablas existen
- Revisar `db/schema_check.py`

### RUT inválido
- Usar `core.utils.normalizar_rut()` antes de guardar
- Usar `core.utils.validar_rut()` para validar
- Formato acepta puntos, guiones o sin ellos, K/k mayúscula

### Stock negativo
- Por defecto se rechaza
- Usar `permitir_negativo=True` solo si hay regla de negocio autorizada y documentada

### Usuario inactivo
- Verificar estado en `dim_usuario.activo`
- Solo administradores pueden autorizar cuentas

## Notas importantes
- **SIN FRONTEND**: No desarrollar UI
- **Stock desde historial**: No guardar stock resultante
- **Sin costo_total**: No agregar a hecho_inventario
- **RUTs como PK**: Sin id_usuario/id_proveedor numéricos
- **FUDO independiente**: No mezclar con hecho_inventario
- **Sin credenciales en código**: Siempre usar .env o secrets
- **Migraciones manuales**: No ejecutar automáticamente en BD remota
