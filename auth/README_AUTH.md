# Autenticación - INKubiertos

## Estado actual
No se implementa un mecanismo de autenticación inseguro. Este módulo documenta cómo integrar con el sistema de autenticación existente.

## Requisitos
- Los usuarios se gestionan en `dim_usuario` con PK `rut_usuario`
- Roles: `Administrador`, `Operario`
- Campo `activo` controla acceso
- Normalización de RUT chileno obligatoria
- NO almacenar contraseñas en texto plano
- Si existe `password_hash`, usarlo con sistema de auth existente

## Integración
Si ya existe sistema de autenticación en la aplicación (Streamlit auth, Supabase Auth, etc.):

1. Autenticar usuario con sistema existente
2. Obtener RUT del usuario autenticado
3. Normalizar RUT con `core.utils.normalizar_rut()`
4. Verificar en `dim_usuario` que existe y está activo
5. Verificar rol con `services.usuarios.UsuariosService.verificar_permisos()`
6. Aplicar restricciones por rol

## Permisos
- **Administrador**: Gestionar usuarios, productos, proveedores, eventos, consultar información financiera, autorizar cuentas
- **Operario**: Registrar movimientos de inventario en su área, consultar información necesaria

## Uso en código
```python
from services.usuarios import UsuariosService
from core.utils import normalizar_rut

usuarios_service = UsuariosService()
rut = normalizar_rut(rut_usuario)
if usuarios_service.puede_registrar_movimientos(rut):
    # Permitir operación
    pass
```

## Notas
- Usuarios inactivos NO pueden registrar movimientos
- Siempre validar con `services.inventario.InventarioService.verificar_permisos_movimiento()`
- RUTs normalizados (sin puntos/guiones, K mayúscula)
- Sin `id_usuario` numérico
