"""Formateo y normalización de valores para la interfaz."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional

from core.areas import area_visible as _area_visible
from core.areas import resolver_area as _resolver_area
from core.stock import clasificar_stock

MESES_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(text[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def fmt_fecha(value: Any) -> str:
    """Devuelve una fecha en formato dd/mm/aaaa."""
    parsed = _to_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else "—"


def fmt_fecha_hora(value: Any) -> str:
    """Devuelve una fecha y hora en formato dd/mm/aaaa HH:MM."""
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                return parsed.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    parsed = _to_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else "—"


def fmt_fecha_larga(value: Any = None) -> str:
    """Devuelve una fecha larga en español, por ejemplo '3 de noviembre de 2026'."""
    parsed = _to_date(value) if value is not None else date.today()
    if not parsed:
        return "—"
    return f"{parsed.day} de {MESES_ES[parsed.month - 1]} de {parsed.year}"


def fmt_numero(value: Any, decimales: int = 0) -> str:
    """Formatea un número con separador de miles chileno."""
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimales <= 0:
        return f"{numero:,.0f}".replace(",", ".")
    return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_cantidad(value: Any) -> str:
    """Formatea cantidades con hasta dos decimales y sin ceros sobrantes."""
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(numero):
        return "—"
    if numero.is_integer():
        return fmt_numero(numero)
    texto = fmt_numero(numero, 2)
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


def fmt_clp(value: Any, compacto: bool = False) -> str:
    """Formatea un monto en pesos chilenos."""
    try:
        monto = float(value)
    except (TypeError, ValueError):
        return "—"

    if compacto:
        absoluto = abs(monto)
        if absoluto >= 1_000_000:
            return f"${monto / 1_000_000:,.1f}M".replace(",", ".").replace(".", ",", 1)
        if absoluto >= 1_000:
            return f"${monto / 1_000:,.0f}K".replace(",", ".")

    return f"${monto:,.0f}".replace(",", ".")


def fmt_pct(value: Any, decimales: int = 0) -> str:
    """Formatea un porcentaje que ya viene expresado en escala 0-100."""
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{numero:.{decimales}f}%".replace(".", ",")


def estado_stock(stock: Any, stock_minimo: Any) -> str:
    """Clasifica el estado de stock según las reglas acordadas (D3-A).

    - Sin stock: stock <= 0
    - Crítico: stock < 70% del mínimo
    - Bajo: 70% <= stock < mínimo
    - Disponible: stock >= mínimo
    """
    return clasificar_stock(stock, stock_minimo)


def resolver_area(value: Any, areas: Optional[Iterable[Dict[str, Any]]] = None) -> Optional[str]:
    """Normaliza el valor de area_asignada a un nombre de área.

    La base real contiene valores mixtos (por ejemplo 'Todas'), por lo que se
    aceptan tanto ids como nombres sin realizar conversiones ni cambios en BD.
    """
    return _resolver_area(value, areas)


def area_visible(value: Any) -> str:
    """Devuelve un área apta para mostrar en la interfaz."""
    return _area_visible(value)

