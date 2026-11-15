"""Límite de intentos fallidos de inicio de sesión por RUT.

El registro vive en memoria del proceso de Streamlit (compartido entre todas
las sesiones del servidor), por lo que abrir otra pestaña no reinicia el
contador. Se pierde al reiniciar la aplicación, lo cual es aceptable para
frenar intentos automatizados de adivinar contraseñas.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 15 * 60
BLOQUEO_SEGUNDOS = 5 * 60

_lock = threading.Lock()
_fallos: Dict[str, List[float]] = {}
_bloqueos: Dict[str, float] = {}


def _clave(rut: str) -> str:
    return "".join(c for c in str(rut or "").upper() if c.isalnum())


def segundos_bloqueo(rut: str, ahora: Optional[float] = None) -> int:
    """Segundos que faltan para poder reintentar; 0 si no está bloqueado."""
    ahora = time.monotonic() if ahora is None else ahora
    clave = _clave(rut)
    with _lock:
        hasta = _bloqueos.get(clave)
        if hasta is None:
            return 0
        if hasta <= ahora:
            _bloqueos.pop(clave, None)
            _fallos.pop(clave, None)
            return 0
        return int(hasta - ahora) + 1


def registrar_fallo(rut: str, ahora: Optional[float] = None) -> None:
    """Anota un intento fallido y bloquea el RUT si supera el máximo."""
    ahora = time.monotonic() if ahora is None else ahora
    clave = _clave(rut)
    with _lock:
        recientes = [t for t in _fallos.get(clave, []) if ahora - t < VENTANA_SEGUNDOS]
        recientes.append(ahora)
        _fallos[clave] = recientes
        if len(recientes) >= MAX_INTENTOS:
            _bloqueos[clave] = ahora + BLOQUEO_SEGUNDOS


def registrar_exito(rut: str) -> None:
    """Limpia el historial de fallos tras un ingreso correcto."""
    clave = _clave(rut)
    with _lock:
        _fallos.pop(clave, None)
        _bloqueos.pop(clave, None)


def reiniciar() -> None:
    """Borra todos los contadores (uso en pruebas)."""
    with _lock:
        _fallos.clear()
        _bloqueos.clear()
