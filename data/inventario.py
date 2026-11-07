"""Lecturas de inventario: stock y historial de movimientos.

El stock se calcula con una consulta paginada de movimientos y la misma
fórmula del servicio de inventario (`core.stock`). No se almacena ni se
modifica nada.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.stock import CONTADORES, clasificar_stock, resumir_movimientos
from data.cache import cache_datos
from data.catalogos import area_id
from data.errors import PERMISOS, ErrorDatos, como_error
from data.permisos import ADMINISTRADOR, area_operario, exigir_sesion
from data.productos import listar_productos
from repositories.fechas import FechasRepository
from repositories.movimientos import MovimientosRepository


@cache_datos(ttl=30)
def _movimientos_snapshot() -> List[Dict[str, Any]]:
    """Movimientos mínimos para calcular stock y contadores (una consulta)."""
    try:
        return MovimientosRepository().stock_agregado()
    except Exception as exc:
        raise como_error(exc) from exc


@cache_datos(ttl=30)
def _resumen_snapshot() -> Dict[Tuple[int, int], Dict[str, float]]:
    return resumir_movimientos(_movimientos_snapshot())


@cache_datos(ttl=30)
def _stock_snapshot() -> Dict[Tuple[int, int], float]:
    return {
        llave: datos["stock"]
        for llave, datos in _resumen_snapshot().items()
    }


def stock_por_producto_area(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[Tuple[int, int], float]:
    """Stock visible para el usuario, agrupado por (producto, área).

    Un operario solo recibe las filas de su área. El administrador recibe todo.
    """
    area_filtro = _resolver_area_consulta(None, usuario)
    snapshot = _stock_snapshot()
    if area_filtro is None:
        return dict(snapshot)
    return {
        llave: stock
        for llave, stock in snapshot.items()
        if llave[1] == int(area_filtro)
    }


def resumen_movimientos_por_producto_area(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[Tuple[int, int], Dict[str, float]]:
    """Stock y contadores por (producto, área) visibles para el usuario.

    Usa exactamente el mismo cálculo que `stock_por_producto_area`, de modo
    que la tabla de inventario nunca pueda mostrar un stock distinto.
    """
    area_filtro = _resolver_area_consulta(None, usuario)
    snapshot = _resumen_snapshot()
    if area_filtro is None:
        return {
            llave: dict(datos)
            for llave, datos in snapshot.items()
        }
    return {
        llave: dict(datos)
        for llave, datos in snapshot.items()
        if llave[1] == int(area_filtro)
    }


def _resolver_area_consulta(
    id_area: Optional[int],
    usuario: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Aplica el área fija del operario; el administrador conserva el filtro."""
    actual = exigir_sesion(usuario)
    area_usuario = area_operario(actual)
    if area_usuario is None:
        return id_area

    area_usuario_id = area_id(area_usuario)
    if area_usuario_id is None:
        raise ErrorDatos(
            "Tu cuenta no tiene un área válida asignada. Contacta al administrador.",
            tipo=PERMISOS,
        )
    return area_usuario_id


def stock_actual(
    id_producto: int,
    id_area: Optional[int] = None,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> float:
    """Stock de un producto.

    Sin área suma todas las áreas (solo administrador). Un operario siempre
    consulta su propia área, aunque envíe otra.
    """
    area_filtro = _resolver_area_consulta(id_area, usuario)
    snapshot = stock_por_producto_area(usuario=usuario)
    producto = int(id_producto)

    if area_filtro is None:
        return sum(
            stock for (id_prod, _), stock in snapshot.items() if id_prod == producto
        )
    return snapshot.get((producto, int(area_filtro)), 0)


def _texto_fecha(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    return texto[:10] if texto else None


@cache_datos(ttl=3600)
def _rango_ids_fecha(
    desde: Optional[str],
    hasta: Optional[str],
) -> Tuple[Optional[int], Optional[int]]:
    try:
        return FechasRepository().rango_ids(desde, hasta)
    except Exception as exc:
        raise como_error(exc) from exc


def ids_fecha_entre(
    desde: Any = None,
    hasta: Any = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Traduce un rango de fechas a ids de `dim_fecha`.

    Si no hay fechas en el rango, no puede haber movimientos en ese período.
    """
    desde_texto = _texto_fecha(desde)
    hasta_texto = _texto_fecha(hasta)
    if desde_texto is None and hasta_texto is None:
        return None, None
    return _rango_ids_fecha(desde_texto, hasta_texto)


@cache_datos(ttl=30)
def _historial(
    id_producto: Optional[int],
    id_area: Optional[int],
    id_tipo_movimiento: Optional[int],
    rut_usuario: Optional[str],
    desde_id: Optional[int],
    hasta_id: Optional[int],
    limite: int,
) -> List[Dict]:
    try:
        return MovimientosRepository().buscar_historial(
            id_producto=id_producto,
            id_area=id_area,
            id_tipo_movimiento=id_tipo_movimiento,
            rut_usuario=rut_usuario,
            id_fecha_desde=desde_id,
            id_fecha_hasta=hasta_id,
            limite=limite,
        )
    except Exception as exc:
        raise como_error(exc) from exc


def historial(
    *,
    id_producto: Optional[int] = None,
    id_area: Optional[int] = None,
    id_tipo_movimiento: Optional[int] = None,
    rut_usuario: Optional[str] = None,
    desde: Any = None,
    hasta: Any = None,
    limite: int = 100,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Historial de movimientos con filtros y área forzada para operarios."""
    area_filtro = _resolver_area_consulta(id_area, usuario)

    desde_id, hasta_id = ids_fecha_entre(desde, hasta)
    if (desde is not None or hasta is not None) and desde_id is None and hasta_id is None:
        return []

    limite_seguro = max(1, min(int(limite), 500))
    return _historial(
        int(id_producto) if id_producto is not None else None,
        area_filtro,
        int(id_tipo_movimiento) if id_tipo_movimiento is not None else None,
        str(rut_usuario) if rut_usuario else None,
        desde_id,
        hasta_id,
        limite_seguro,
    )


def ultimos_movimientos(
    limite: int = 10,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Atajo para los movimientos más recientes visibles para el usuario."""
    return historial(limite=limite, usuario=usuario)


def _numero_opcional(value: Any) -> Optional[float]:
    """Convierte un valor numérico; None si no es un número finito."""
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _costo_positivo(value: Any) -> Optional[float]:
    """Costo base utilizable para valorizar; None si no está definido."""
    numero = _numero_opcional(value)
    return numero if numero is not None and numero > 0 else None


def _detalle_por_producto(
    snapshot: Dict[Tuple[int, int], Dict[str, float]],
) -> Dict[int, Dict[str, float]]:
    """Suma stock y contadores del snapshot (producto, área) por producto.

    Para un operario el snapshot ya viene filtrado a su área, por lo que esta
    suma representa su stock. Para un administrador representa el total global.
    """
    acumulado: Dict[int, Dict[str, float]] = {}
    for (id_producto, _), datos in snapshot.items():
        fila = acumulado.setdefault(
            id_producto,
            {"stock": 0.0, **{contador: 0.0 for contador in CONTADORES}},
        )
        fila["stock"] += float(datos.get("stock") or 0)
        for contador in CONTADORES:
            fila[contador] += float(datos.get(contador) or 0)
    return acumulado


def inventario_visible(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Read model del inventario visible para el usuario.

    Reutiliza el snapshot de stock y la clasificación compartida (`core.stock`).
    El administrador ve todos los productos activos; un operario solo ve los
    productos con movimientos en su área. No se inventan productos ni stock.
    """
    actual = exigir_sesion(usuario)
    es_administrador = actual.get("rol") == ADMINISTRADOR
    snapshot = resumen_movimientos_por_producto_area(usuario=actual)

    # Un operario sin movimientos en su área no tiene inventario que mostrar.
    if not es_administrador and not snapshot:
        return []

    productos = listar_productos(solo_activos=True)
    detalle_por_producto = _detalle_por_producto(snapshot)
    filas: List[Dict[str, Any]] = []

    for producto in productos:
        try:
            id_producto = int(producto.get("id_producto"))
        except (TypeError, ValueError):
            continue

        if not es_administrador and id_producto not in detalle_por_producto:
            continue

        detalle = detalle_por_producto.get(id_producto, {})
        stock = round(float(detalle.get("stock") or 0.0), 4)
        entradas = round(float(detalle.get("entradas") or 0.0), 4)
        salidas = round(float(detalle.get("salidas") or 0.0), 4)
        mermas = round(float(detalle.get("mermas") or 0.0), 4)
        ajustes = round(
            float(detalle.get("ajustes_positivos") or 0.0)
            - float(detalle.get("ajustes_negativos") or 0.0),
            4,
        )
        minimo = _numero_opcional(producto.get("stock_minimo"))
        maximo = _numero_opcional(producto.get("stock_maximo"))
        nombre = str(producto.get("nombre_producto") or "").strip() or "Sin nombre"
        categoria = str(producto.get("categoria") or "").strip() or "Sin categoría"
        unidad = str(producto.get("unidad_medida") or "").strip() or "—"

        filas.append(
            {
                "id_producto": id_producto,
                "nombre": nombre,
                "categoria": categoria,
                "unidad": unidad,
                "stock_actual": stock,
                "entradas": entradas,
                "salidas": salidas,
                "mermas": mermas,
                "ajustes": ajustes,
                "ajustes_positivos": round(
                    float(detalle.get("ajustes_positivos") or 0.0), 4
                ),
                "ajustes_negativos": round(
                    float(detalle.get("ajustes_negativos") or 0.0), 4
                ),
                "stock_minimo": minimo,
                "stock_maximo": maximo,
                "costo_base": _costo_positivo(producto.get("costo_base")),
                "estado": clasificar_stock(stock, minimo if minimo is not None else 0),
            }
        )

    filas.sort(key=lambda fila: (fila["nombre"].casefold(), fila["id_producto"]))
    return filas


def resumen_inventario(
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Indicadores del dashboard calculados sobre el inventario visible.

    El valor estimado solo incluye productos con costo base positivo y stock
    positivo. No se usan cifras simuladas ni se duplica la fórmula de stock.
    """
    filas = inventario_visible(usuario=usuario)

    conteos = {"Disponible": 0, "Bajo": 0, "Crítico": 0, "Sin stock": 0}
    valor_estimado = 0.0
    productos_con_costo = 0
    productos_valorizados = 0

    for fila in filas:
        estado = fila.get("estado")
        if estado in conteos:
            conteos[estado] += 1

        costo = fila.get("costo_base")
        if costo is None:
            continue
        productos_con_costo += 1

        stock = fila.get("stock_actual")
        if stock is not None and stock > 0:
            valor_estimado += float(stock) * float(costo)
            productos_valorizados += 1

    return {
        "total_productos": len(filas),
        "disponibles": conteos["Disponible"],
        "bajos": conteos["Bajo"],
        "criticos": conteos["Crítico"],
        "sin_stock": conteos["Sin stock"],
        "valor_estimado": valor_estimado if productos_valorizados else None,
        "productos_con_costo": productos_con_costo,
        "productos_valorizados": productos_valorizados,
    }


def filtrar_inventario(
    filas: List[Dict[str, Any]],
    *,
    texto: str = "",
    categoria: Optional[str] = None,
    estado: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aplica búsqueda y filtros sobre las filas ya autorizadas.

    Se ejecuta en memoria sobre el read model, después de aplicar los permisos,
    de modo que un filtro no pueda ampliar el alcance del usuario.
    """
    termino = (texto or "").strip().casefold()
    categoria_filtro = (categoria or "").strip()
    estado_filtro = (estado or "").strip()
    sin_filtro_categoria = categoria_filtro.casefold() in {"", "todas", "todos"}
    sin_filtro_estado = estado_filtro.casefold() in {"", "todos", "todas"}

    resultado: List[Dict[str, Any]] = []
    for fila in filas:
        nombre = str(fila.get("nombre") or "").casefold()
        categoria_fila = str(fila.get("categoria") or "").casefold()

        if termino and termino not in nombre and termino not in categoria_fila:
            continue
        if not sin_filtro_categoria and categoria_fila != categoria_filtro.casefold():
            continue
        if not sin_filtro_estado and str(fila.get("estado") or "") != estado_filtro:
            continue

        resultado.append(fila)

    return resultado
