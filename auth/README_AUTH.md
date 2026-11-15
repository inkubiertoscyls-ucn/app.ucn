# Autenticación - INKubiertos

## Cómo funciona
- Los usuarios viven en `dim_usuario` (PK `rut_usuario`, RUT normalizado sin puntos ni guion).
- El ingreso es con **RUT + contraseña**. Las contraseñas se guardan solo como hash
  **Argon2id** (`core/auth_password.py`); nunca en texto plano.
- Roles: `Administrador` y `Operario`. El campo `activo` controla el acceso.

## Flujo
1. **Registro público** (`views/auth.py`): solo crea cuentas `Operario`, siempre inactivas.
2. Un **administrador** activa la cuenta desde la pantalla *Usuarios*.
3. **Login** (`components/auth.py` → `UsuariosService.autenticar`):
   - Se valida el formato del RUT antes de consultar la base de datos.
   - Se verifica la contraseña **antes** de informar si la cuenta está inactiva, para no revelar
     qué RUT están registrados.
   - Tras 5 intentos fallidos para un RUT, se bloquea durante 5 minutos (`core/intentos_login.py`).
4. **Sesión** (`ui/state.py`):
   - Se cierra tras `SESSION_TIMEOUT_MINUTES` minutos sin actividad (60 por defecto).
   - Cada minuto se relee la cuenta: si fue desactivada se cierra la sesión, y si cambió el rol o
     el área se actualiza.

## Primer administrador
```bash
python scripts/init_admin.py
```
Solo funciona si todavía no existe ningún administrador.

## Permisos
- **Administrador**: usuarios, productos, proveedores, eventos, ventas FUDO y rentabilidad.
- **Operario**: registra y consulta movimientos solo de su área.

Los permisos se validan en la capa de datos (`data/permisos.py`) y en los servicios, no solo en las
pantallas. Activar, desactivar o modificar una cuenta exige indicar el administrador que autoriza.

## Recuperación de acceso
No hay restablecimiento por correo. Un administrador debe gestionar la cuenta.
