"""Reglas de cálculo y clasificación de stock.

Se extraen aquí para que el servicio de inventario y la capa de datos del
frontend usen exactamente la misma fórmula, sin duplicar lógica.
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict, Iterable, Mapping, Tuple

# Contadores que expone el inventario para cada producto.
CONTADORES = (
    "entradas",
    "salidas",
    "mermas",
    "ajustes_positivos",
    "ajustes_negativos",
)

_TIPO_A_CONTADOR = {
    "entrada": "entradas",
    "salida": "salidas",
    "merma": "mermas",
    "ajuste positivo": "ajustes_positivos",
    "ajuste negativo": "ajustes_negativos",
}


def normalizar_tipo_movimiento(valor: Any) -> str:
    """Normaliza el nombre de un tipo de movimiento para compararlo."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    sin_tildes = "".join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    )
    return " ".join(sin_tildes.casefold().split())


def _delta_movimiento(movimiento: Mapping[str, Any]) -> float:
    """Cantidad con signo de un movimiento según el factor del tipo."""
    cantidad = movimiento.get("cantidad") or 0
    tipo = movimiento.get("dim_tipo_movimiento") or {}
    factor = tipo.get("factor_stock", 0) if isinstance(tipo, Mapping) else 0
    return cantidad * (factor or 0)


def calcular_stock(movimientos: Iterable[Mapping[str, Any]]) -> float:
    """Calcula el stock sumando cantidad * factor_stock de cada movimiento."""
    total = 0
    for movimiento in movimientos:
        total += _delta_movimiento(movimiento)
    return total


def calcular_stock_agregado(
    movimientos: Iterable[Mapping[str, Any]],
) -> Dict[Tuple[int, int], float]:
    """Agrupa el stock por (id_producto, id_area) en una sola pasada.

    Se usa para reemplazar el cálculo N+1: una consulta de movimientos permite
    responder el stock de todos los productos y áreas de una vez.
    """
    resultado: Dict[Tuple[int, int], float] = {}
    for movimiento in movimientos:
        id_producto = movimiento.get("id_producto")
        id_area = movimiento.get("id_area")
        if id_producto is None or id_area is None:
            continue
        llave = (int(id_producto), int(id_area))
        resultado[llave] = resultado.get(llave, 0) + _delta_movimiento(movimiento)
    return resultado


def resumir_movimientos(
    movimientos: Iterable[Mapping[str, Any]],
) -> Dict[Tuple[int, int], Dict[str, float]]:
    """Agrupa stock y contadores por (producto, área) en una sola pasada.

    El stock usa `cantidad * factor_stock`, igual que `calcular_stock`. Los
    contadores clasifican por nombre del tipo de movimiento y conservan la
    cantidad informada (siempre positiva). Un tipo desconocido sigue sumando
    al stock, pero no se atribuye a ningún contador.
    """
    resultado: Dict[Tuple[int, int], Dict[str, float]] = {}
    for movimiento in movimientos:
        id_producto = movimiento.get("id_producto")
        id_area = movimiento.get("id_area")
        if id_producto is None or id_area is None:
            continue

        llave = (int(id_producto), int(id_area))
        fila = resultado.setdefault(
            llave,
            {"stock": 0.0, **{contador: 0.0 for contador in CONTADORES}},
        )
        fila["stock"] += _delta_movimiento(movimiento)

        tipo = movimiento.get("dim_tipo_movimiento") or {}
        nombre = normalizar_tipo_movimiento(
            tipo.get("tipo_movimiento") if isinstance(tipo, Mapping) else ""
        )
        contador = _TIPO_A_CONTADOR.get(nombre)
        if contador is None:
            continue
        try:
            cantidad = abs(float(movimiento.get("cantidad") or 0))
        except (TypeError, ValueError):
            cantidad = 0.0
        fila[contador] += cantidad

    return resultado


def clasificar_stock(stock: Any, stock_minimo: Any) -> str:
    """Clasifica el estado de stock según las reglas acordadas (D3-A).

    - Sin stock: stock <= 0
    - Crítico: stock < 70% del mínimo
    - Bajo: 70% <= stock < mínimo
    - Disponible: stock >= mínimo
    """
    try:
        actual = float(stock)
    except (TypeError, ValueError):
        actual = 0.0
    try:
        minimo = float(stock_minimo)
    except (TypeError, ValueError):
        minimo = 0.0

    if actual <= 0:
        return "Sin stock"
    if minimo <= 0:
        return "Disponible"
    if actual < minimo * 0.7:
        return "Crítico"
    if actual < minimo:
        return "Bajo"
    return "Disponible"
