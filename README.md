# INKubiertos - Backend

Backend para el sistema de control de inventario de INKubiertos (Restobar, La Serena, Chile).

## Objetivo
Mejorar el control de inventario mediante registro de entradas/salidas, calcular stock por producto/área desde historial, y preparar integración con ventas exportadas desde FUDO para análisis de rentabilidad.

## Estructura
```
inkubiertos/
├── auth/           # Documentación de autenticación
├── config/         # Configuración (env/secrets)
├── core/           # Utilidades, validadores, excepciones
├── db/             # Cliente Supabase, migraciones, verificación esquema
├── repositories/   # Acceso a datos por tabla
├── services/       # Reglas de negocio (inventario, productos, usuarios, FUDO)
├── tests/          # Pruebas automatizadas
└── utils/          # Utilidades adicionales
```

## Requisitos
- Python 3.10+
- Cuenta Supabase (URL y keys)
- Streamlit (opcional para UI, pero se integra con él)

## Instalación
1. Clonar/descargar proyecto
2. Crear entorno virtual: `python -m venv .venv`
3. Activar entorno:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
4. Instalar dependencias: `pip install -r requirements.txt`
5. Configurar variables de entorno:
   - Copiar `.env.example` a `.env` y completar valores
   - O usar `.streamlit/secrets.toml` si se ejecuta con Streamlit

## Configuración de Supabase
**IMPORTANTE:** Nunca escribir claves en código. Usar `.env` o `st.secrets`.

Variables requeridas:
- `SUPABASE_URL`
- `SUPABASE_KEY` (anon key)
- `SUPABASE_SERVICE_ROLE_KEY` (opcional, para operaciones administrativas)

## Base de datos
El esquema esperado está documentado en `db/migrations/001_initial_schema.sql`. 

**NO** se ejecutarán migraciones automáticamente sobre la BD remota. 
Para aplicar cambios:
1. Revisar migraciones
2. Ejecutar manualmente en Supabase SQL Editor
3. Verificar con `db/schema_check.py`

### Tablas principales
- `dim_fecha`, `dim_area`, `dim_usuario` (PK: `rut_usuario`), `dim_proveedor` (PK: `rut_proveedor`), `dim_producto`, `dim_tipo_movimiento`, `dim_evento`
- `hecho_inventario` (sin `costo_total`)
- `hecho_venta_fudo` (independiente)

**Restricciones importantes:**
- `dim_producto` NO tiene `area_habitual`
- `dim_usuario.rut_usuario` es PK (sin `id_usuario`)
- `dim_proveedor.rut_proveedor` es PK (sin `id_proveedor`)
- `hecho_inventario` NO debe tener `costo_total`

## Uso del backend
Los módulos están organizados para ser importados desde Streamlit u otros scripts:

```python
from config.settings import get_settings
from db.supabase_client import get_supabase_client
from services.inventario import InventarioService
from core.utils import normalizar_rut, validar_rut
```

## Pruebas
```bash
pytest tests/ -v
```

Las pruebas usan datos ficticios. Si no hay acceso a Supabase o archivos FUDO, las pruebas se marcarán como `skipped` con justificación.

## Notas importantes
- **Sin frontend**: Este repositorio solo contiene backend. No modificar UI.
- **Stock**: Se calcula desde historial de `hecho_inventario` usando `factor_stock` de `dim_tipo_movimiento`. No se guarda stock resultante.
- **Permisos**: `Administrador` vs `Operario`. Usuarios inactivos no pueden registrar movimientos.
- **FUDO**: Importador flexible - requiere mapeo de columnas ya que formato no está definido.
- **Seguridad**: Validación de RUT chileno, prevención de stock negativo (configurable), operaciones atómicas donde sea posible.

## Pendientes
- Archivo real de exportación FUDO (Excel/CSV) para afinar importador
- Definición de mecanismo de autenticación existente (si aplica)
- Configuración de reglas específicas de negocio (autorización para stock negativo)
- Verificación de esquema real en Supabase
