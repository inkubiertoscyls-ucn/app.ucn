"""Alertas de stock calculadas sobre el inventario visible.

Reutiliza el read model de inventario y el historial. "Recuperados hoy" sigue
la definición D4-A: una entrada del día que deja el producto en o sobre su
mínimo, partiendo de una situación bajo el mínimo.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from data.catalogos import listar_areas, listar_tipos_movimiento
from data.inventario import historial, inventario_visible


def _normalizar(texto: Any) -> str:
    return " ".join(str(texto or "").strip().casefold().split())


def _id_int(valor: Any) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _recuperados(
    filas: List[Dict[str, Any]],
    movimientos: List[Dict[str, Any]],
    tipos: Dict[int, Dict[str, Any]],
    areas: Dict[int, str],
) -> List[Dict[str, Any]]:
    """Detecta entradas de hoy que sacaron al producto de bajo el mínimo."""
    visibles = {fila.get("id_producto"): fila for fila in filas}
    por_producto: Dict[int, List[Dict[str, Any]]] = {}

    for movimiento in movimientos:
        id_producto = _id_int(movimiento.get("id_producto"))
        if id_producto in visibles:
            por_producto.setdefault(id_producto, []).append(movimiento)

    recuperados: List[Dict[str, Any]] = []
    for id_producto, movimientos_producto in por_producto.items():
        fila = visibles[id_producto]
        minimo = fila.get("stock_minimo") or 0
        if minimo <= 0:
            continue

        ordenados = sorted(
            movimientos_producto,
            key=lambda movimiento: (
                str(movimiento.get("fecha_hora_registro") or ""),
                _id_int(movimiento.get("id_hecho_inventario")),
            ),
        )

        delta_total = 0.0
        for movimiento in ordenados:
            tipo = tipos.get(_id_int(movimiento.get("id_tipo_movimiento"))) or {}
            try:
                factor = int(tipo.get("factor_stock"))
            except (TypeError, ValueError):
                factor = 0
            try:
                cantidad = float(movimiento.get("cantidad") or 0)
            except (TypeError, ValueError):
                cantidad = 0.0
            delta_total += cantidad * factor

        try:
            stock_actual = float(fila.get("stock_actual") or 0)
        except (TypeError, ValueError):
            stock_actual = 0.0
        stock = stock_actual - delta_total

        for movimiento in ordenados:
            tipo = tipos.get(_id_int(movimiento.get("id_tipo_movimiento"))) or {}
            try:
                factor = int(tipo.get("factor_stock"))
            except (TypeError, ValueError):
                factor = 0
            try:
                cantidad = float(movimiento.get("cantidad") or 0)
            except (TypeError, ValueError):
                cantidad = 0.0

            anterior = stock
            stock += cantidad * factor
            es_entrada = _normalizar(tipo.get("tipo_movimiento")) == "entrada"
            if es_entrada and anterior < float(minimo) <= stock:
                recuperados.append(
                    {
                        "id_producto": id_producto,
                        "producto": fila.get("nombre") or "Sin nombre",
                        "categoria": fila.get("categoria") or "Sin categoría",
                        "unidad": fila.get("unidad") or "",
                        "area": areas.get(_id_int(movimiento.get("id_area")), "Sin área"),
                        "stock_actual": stock_actual,
                        "stock_minimo": float(minimo),
                        "stock_despues": stock,
                        "estado": fila.get("estado"),
                        "recuperado_a": movimiento.get("fecha_hora_registro"),
                        "cantidad": cantidad,
                        "rut_usuario": str(movimiento.get("rut_usuario") or ""),
                    }
                )
                break

    recuperados.sort(
        key=lambda fila: str(fila.get("recuperado_a") or ""),
        reverse=True,
    )
    return recuperados


def resumen_alertas(
    *,
    usuario: Optional[Dict[str, Any]] = None,
    hoy: Optional[date] = None,
) -> Dict[str, Any]:
    """Agrupa sin stock, críticos, bajos y recuperados del día."""
    dia = hoy or date.today()
    filas = inventario_visible(usuario=usuario)
    sin_stock = [fila for fila in filas if fila.get("estado") == "Sin stock"]
    criticos = [fila for fila in filas if fila.get("estado") == "Crítico"]
    bajos = [fila for fila in filas if fila.get("estado") == "Bajo"]

    movimientos = historial(
        desde=dia,
        hasta=dia,
        limite=500,
        usuario=usuario,
    )
    tipos = {
        _id_int(tipo.get("id_tipo_movimiento")): tipo
        for tipo in listar_tipos_movimiento(incluir_inactivos=True)
    }
    areas = {
        _id_int(area.get("id_area")): str(area.get("nombre_area") or "Sin área")
        for area in listar_areas(incluir_inactivas=True)
    }

    recuperados = _recuperados(filas, movimientos, tipos, areas)

    return {
        "fecha": dia,
        "total_productos": len(filas),
        "sin_stock": sin_stock,
        "criticos": criticos,
        "bajos": bajos,
        "recuperados": recuperados,
        "conteos": {
            "sin_stock": len(sin_stock),
            "criticos": len(criticos),
            "bajos": len(bajos),
            "recuperados": len(recuperados),
        },
    }
