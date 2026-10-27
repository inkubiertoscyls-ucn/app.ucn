"""
Utility functions for INKubiertos.
Includes Chilean RUT validation and normalization.
"""
import re
from .exceptions import InvalidRUTError


def limpiar_rut(rut: str) -> str:
    """
    Clean RUT: remove dots, dashes, spaces.
    Convert K/k to uppercase.
    """
    if not rut:
        return ""
    rut = str(rut).strip().upper()
    rut = rut.replace(".", "").replace("-", "").replace(" ", "")
    return rut


def normalizar_rut(rut: str) -> str:
    """
    Normalize Chilean RUT.
    Returns clean RUT without dots/dashes, with verification digit uppercase.
    """
    if rut is None:
        raise InvalidRUTError("RUT inválido")
    
    limpio = limpiar_rut(rut)
    if not limpio:
        raise InvalidRUTError("RUT inválido")
    if len(limpio) < 2:
        raise InvalidRUTError("RUT inválido")
    if len(limpio) < 8:  # RUT chileno mínimo típicamente tiene al menos 7-8 caracteres
        raise InvalidRUTError("RUT inválido")
    
    # Body + verification digit
    cuerpo = limpio[:-1]
    dv = limpio[-1]
    
    # Validate body is numeric
    if not cuerpo.isdigit():
        raise InvalidRUTError("RUT inválido: cuerpo debe ser numérico")
    if dv not in "0123456789K":
        raise InvalidRUTError("RUT inválido: dígito verificador inválido")
    if len(cuerpo) < 7:  # cuerpo debe tener al menos 7 dígitos
        raise InvalidRUTError("RUT inválido")
    
    return cuerpo + dv


def validar_rut(rut: str) -> bool:
    """
    Validate Chilean RUT using check digit algorithm.
    """
    try:
        rut_norm = normalizar_rut(rut)
        cuerpo = rut_norm[:-1]
        dv = rut_norm[-1]
        
        suma = 0
        multiplo = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo += 1
            if multiplo == 8:
                multiplo = 2
        
        resto = suma % 11
        dv_esperado = 11 - resto
        
        if dv_esperado == 11:
            dv_esperado_calc = "0"
        elif dv_esperado == 10:
            dv_esperado_calc = "K"
        else:
            dv_esperado_calc = str(dv_esperado)
        
        return dv == dv_esperado_calc
    except Exception:
        return False


def formatear_rut(rut: str) -> str:
    """
    Format RUT as XX.XXX.XXX-X
    """
    try:
        rut_norm = normalizar_rut(rut)
        cuerpo = rut_norm[:-1]
        dv = rut_norm[-1]
        # Add dots from right to left
        cuerpo_fmt = ""
        for i, c in enumerate(reversed(cuerpo)):
            if i > 0 and i % 3 == 0:
                cuerpo_fmt = "." + cuerpo_fmt
            cuerpo_fmt = c + cuerpo_fmt
        return f"{cuerpo_fmt}-{dv}"
    except Exception:
        return rut


def es_numero_positivo(valor) -> bool:
    """Check if value is a positive number."""
    try:
        num = float(valor)
        return num > 0
    except Exception:
        return False


def es_numero_no_negativo(valor) -> bool:
    """Check if value is non-negative number."""
    try:
        num = float(valor)
        return num >= 0
    except Exception:
        return False
