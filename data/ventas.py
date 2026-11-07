"""Capa de datos para ventas FUDO y rentabilidad.

Todas las funciones de lectura y escritura exigen rol Administrador, también
en esta capa. Los cálculos de costo, utilidad y margen se hacen únicamente
sobre ventas con producto vinculado, cantidad informada y `costo_base` válido.
Las ventas restantes se informan aparte y nunca se asumen como utilidad cero.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from data.cache import cache_datos, limpiar_cache
from data.catalogos import listar_eventos
from data.errors import (
    NO_ENCONTRADO,
    VALIDACION,
    ErrorDatos,
    como_error,
)
from data.permisos import exigir_admin
from data.productos import listar_productos
from repositories.productos import ProductosRepository
from repositories.ventas import VentasFudoRepository

LIMITE_RENTABILIDAD = 10000


def _fecha_texto(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    return texto[:10] if texto else None


def _monto(valor: Any) -> Optional[float]:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _costo_valido(valor: Any) -> Optional[float]:
    numero = _monto(valor)
    return numero if numero is not None and numero > 0 else None


def _entero(valor: Any) -> Optional[int]:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------
# Lecturas
# ----------------------------------------------------------------------
@cache_datos(ttl=60)
def _ventas_recientes(limite: int) -> List[Dict]:
    try:
        return VentasFudoRepository().listar_recientes(limite)
    except Exception as exc:
        raise como_error(exc) from exc


def listar_ventas_recientes(
    limite: int = 50,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Ventas FUDO recientes sin el campo pesado `datos_raw`."""
    exigir_admin(usuario)
    limite_seguro = max(1, min(int(limite), 200))
    return _ventas_recientes(limite_seguro)


@cache_datos(ttl=60)
def _ventas_filtradas(
    desde: Optional[str],
    hasta: Optional[str],
    solo_pendientes: bool,
    texto: str,
    id_evento: Optional[int],
    limite: int,
) -> List[Dict]:
    try:
        return VentasFudoRepository().listar(
            desde=desde,
            hasta=hasta,
            solo_pendientes=solo_pendientes,
            texto=texto,
            id_evento=id_evento,
            limite=limite,
        )
    except Exception as exc:
        raise como_error(exc) from exc


def listar_ventas(
    *,
    desde: Any = None,
    hasta: Any = None,
    solo_pendientes: bool = False,
    texto: str = "",
    id_evento: Optional[int] = None,
    limite: int = 200,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Lista ventas filtradas por fecha, evento, texto o estado de vinculación."""
    exigir_admin(usuario)
    evento = _entero(id_evento) if id_evento not in (None, "", 0, "0") else None
    limite_seguro = max(1, min(int(limite), 500))
    return _ventas_filtradas(
        _fecha_texto(desde),
        _fecha_texto(hasta),
        bool(solo_pendientes),
        str(texto or "").strip(),
        evento,
        limite_seguro,
    )


def listar_ventas_pendientes(
    limite: int = 200,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Ventas que todavía no tienen producto vinculado."""
    return listar_ventas(
        solo_pendientes=True,
        limite=limite,
        usuario=usuario,
    )


# ----------------------------------------------------------------------
# Vinculación manual de productos
# ----------------------------------------------------------------------
def _producto_para_vincular(
    id_producto: Any,
    *,
    usuario: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    exigir_admin(usuario)
    id_entero = _entero(id_producto)
    if id_entero is None:
        raise ErrorDatos("Selecciona un producto para vincular.", tipo=VALIDACION)

    try:
        producto = ProductosRepository().get_by_id("id_producto", id_entero)
    except Exception as exc:
        raise como_error(exc) from exc

    if not producto:
        raise ErrorDatos(
            "El producto seleccionado ya no está disponible.",
            tipo=NO_ENCONTRADO,
        )
    return producto


def vincular_venta(
    id_venta_fudo: Any,
    id_producto: Any,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Vincula una venta concreta con un producto, sin tocar sus datos originales."""
    id_venta = _entero(id_venta_fudo)
    if id_venta is None:
        raise ErrorDatos("La venta seleccionada no es válida.", tipo=VALIDACION)
    producto = _producto_para_vincular(id_producto, usuario=usuario)

    try:
        actualizadas = VentasFudoRepository().actualizar_vinculacion(
            id_venta, int(producto.get("id_producto"))
        )
    except Exception as exc:
        raise como_error(exc) from exc

    limpiar_cache()
    return {
        "id_venta_fudo": id_venta,
        "id_producto": int(producto.get("id_producto")),
        "producto": str(producto.get("nombre_producto") or "").strip(),
        "actualizadas": len(actualizadas),
    }


def vincular_ventas_por_nombre(
    producto_identificado: str,
    id_producto: Any,
    *,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Vincula todas las ventas pendientes con el mismo nombre original de FUDO.

    Solo se modifica `id_producto_relacionado`. El nombre original, la fecha,
    el monto y `datos_raw` se conservan intactos.
    """
    nombre = str(producto_identificado or "").strip()
    if not nombre:
        raise ErrorDatos(
            "El nombre de producto de FUDO no es válido.",
            tipo=VALIDACION,
        )
    producto = _producto_para_vincular(id_producto, usuario=usuario)

    try:
        ids = VentasFudoRepository().vincular_por_producto_identificado(
            nombre, int(producto.get("id_producto"))
        )
    except Exception as exc:
        raise como_error(exc) from exc

    if not ids:
        raise ErrorDatos(
            "No hay ventas pendientes con ese nombre. Actualiza la lista e "
            "intenta nuevamente.",
            tipo=NO_ENCONTRADO,
        )

    limpiar_cache()
    return {
        "producto_identificado": nombre,
        "id_producto": int(producto.get("id_producto")),
        "producto": str(producto.get("nombre_producto") or "").strip(),
        "vinculadas": len(ids),
    }


# ----------------------------------------------------------------------
# Rentabilidad estimada
# ----------------------------------------------------------------------
def _acumulador() -> Dict[str, Any]:
    return {
        "registros": 0,
        "cantidad": 0.0,
        "ventas": 0.0,
        "costo": 0.0,
        "utilidad": 0.0,
    }


def _cerrar_acumulador(datos: Dict[str, Any]) -> Dict[str, Any]:
    ventas = float(datos.get("ventas") or 0)
    utilidad = float(datos.get("utilidad") or 0)
    datos["ventas"] = round(ventas, 2)
    datos["costo"] = round(float(datos.get("costo") or 0), 2)
    datos["utilidad"] = round(utilidad, 2)
    datos["cantidad"] = round(float(datos.get("cantidad") or 0), 4)
    datos["margen"] = (
        round(utilidad / ventas * 100, 2) if ventas > 0 else None
    )
    return datos


def calcular_resumen_rentabilidad(
    ventas: Iterable[Dict[str, Any]],
    productos: Optional[Iterable[Dict[str, Any]]] = None,
    eventos: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    truncado: bool = False,
) -> Dict[str, Any]:
    """Calcula indicadores y agrupaciones a partir de ventas ya leídas.

    Es una función pura para poder probar los cálculos con datos controlados.
    """
    mapa_productos: Dict[int, Dict[str, Any]] = {}
    for producto in productos or []:
        id_producto = _entero(producto.get("id_producto"))
        if id_producto is None:
            continue
        mapa_productos[id_producto] = {
            "nombre": str(
                producto.get("nombre_producto") or "Sin nombre"
            ).strip()
            or "Sin nombre",
            "categoria": str(
                producto.get("categoria") or "Sin categoría"
            ).strip()
            or "Sin categoría",
            "costo": _costo_valido(producto.get("costo_base")),
        }

    mapa_eventos: Dict[int, str] = {}
    for evento in eventos or []:
        id_evento = _entero(evento.get("id_evento"))
        if id_evento is None:
            continue
        mapa_eventos[id_evento] = (
            str(evento.get("nombre_evento") or "").strip()
            or f"Evento {id_evento}"
        )

    total_registros = 0
    registros_con_total = 0
    registros_sin_total = 0
    registros_con_cantidad = 0
    registros_sin_cantidad = 0
    monto_total = 0.0
    cantidad_total = 0.0

    ventas_identificadas = 0
    ventas_pendientes = 0
    monto_pendiente = 0.0

    ventas_con_costo = 0
    monto_con_costo = 0.0
    costo_estimado = 0.0
    utilidad_estimada = 0.0

    ventas_identificadas_sin_costo = 0
    monto_identificado_sin_costo = 0.0

    por_categoria: Dict[str, Dict[str, Any]] = {}
    por_producto: Dict[int, Dict[str, Any]] = {}
    sin_costo: Dict[str, Dict[str, Any]] = {}
    eventos_agrupados: Dict[Optional[int], Dict[str, Any]] = {}

    for venta in ventas:
        total_registros += 1
        total = _monto(venta.get("total_venta"))
        cantidad = _monto(venta.get("cantidad_total"))
        id_producto = _entero(venta.get("id_producto_relacionado"))
        id_evento = _entero(venta.get("id_evento"))

        if total is not None:
            registros_con_total += 1
            monto_total += total
        else:
            registros_sin_total += 1

        if cantidad is not None:
            registros_con_cantidad += 1
            cantidad_total += cantidad
        else:
            registros_sin_cantidad += 1

        grupo_evento = eventos_agrupados.setdefault(
            id_evento,
            {
                "id_evento": id_evento,
                "evento": (
                    mapa_eventos.get(id_evento, f"Evento {id_evento}")
                    if id_evento is not None
                    else "Sin evento asignado"
                ),
                "registros": 0,
                "ventas": 0.0,
                "identificadas": 0,
                "pendientes": 0,
            },
        )
        grupo_evento["registros"] += 1
        if total is not None:
            grupo_evento["ventas"] += total

        if id_producto is None:
            ventas_pendientes += 1
            grupo_evento["pendientes"] += 1
            if total is not None:
                monto_pendiente += total
            continue

        ventas_identificadas += 1
        grupo_evento["identificadas"] += 1
        producto = mapa_productos.get(id_producto)
        costo_base = producto.get("costo") if producto else None

        nombre_producto = (
            producto["nombre"]
            if producto
            else str(venta.get("producto_identificado") or "Producto no disponible").strip()
        )
        categoria = producto["categoria"] if producto else "Sin categoría"

        motivos: List[str] = []
        if producto is None:
            motivos.append("El producto vinculado ya no existe.")
        elif costo_base is None:
            motivos.append("Sin costo base válido.")
        if cantidad is None:
            motivos.append("Sin cantidad informada.")
        elif cantidad <= 0:
            motivos.append("Cantidad no válida para estimar el costo.")
        if total is None:
            motivos.append("Sin total informado.")

        if motivos:
            ventas_identificadas_sin_costo += 1
            if total is not None:
                monto_identificado_sin_costo += total
            clave = nombre_producto or "Sin producto"
            grupo = sin_costo.setdefault(
                clave,
                {
                    "producto": clave,
                    "categoria": categoria,
                    "registros": 0,
                    "monto": 0.0,
                    "motivos": [],
                },
            )
            grupo["registros"] += 1
            if total is not None:
                grupo["monto"] += total
            for motivo in motivos:
                if motivo not in grupo["motivos"]:
                    grupo["motivos"].append(motivo)
            continue

        costo_fila = float(costo_base) * float(cantidad)
        utilidad_fila = float(total) - costo_fila
        ventas_con_costo += 1
        monto_con_costo += float(total)
        costo_estimado += costo_fila
        utilidad_estimada += utilidad_fila

        acumulado_categoria = por_categoria.setdefault(
            categoria, {**_acumulador(), "categoria": categoria}
        )
        acumulado_categoria["registros"] += 1
        acumulado_categoria["cantidad"] += float(cantidad)
        acumulado_categoria["ventas"] += float(total)
        acumulado_categoria["costo"] += costo_fila
        acumulado_categoria["utilidad"] += utilidad_fila

        acumulado_producto = por_producto.setdefault(
            id_producto,
            {
                **_acumulador(),
                "id_producto": id_producto,
                "producto": nombre_producto,
                "categoria": categoria,
            },
        )
        acumulado_producto["registros"] += 1
        acumulado_producto["cantidad"] += float(cantidad)
        acumulado_producto["ventas"] += float(total)
        acumulado_producto["costo"] += costo_fila
        acumulado_producto["utilidad"] += utilidad_fila

    categorias = [
        _cerrar_acumulador(datos)
        for datos in por_categoria.values()
    ]
    categorias.sort(key=lambda fila: (-fila["utilidad"], fila["categoria"].casefold()))

    productos_agrupados = [
        _cerrar_acumulador(datos)
        for datos in por_producto.values()
    ]
    productos_agrupados.sort(
        key=lambda fila: (-fila["utilidad"], fila["producto"].casefold())
    )

    sin_costo_detalle = []
    for grupo in sin_costo.values():
        grupo["monto"] = round(float(grupo["monto"]), 2)
        grupo["motivo"] = " ".join(grupo["motivos"])
        sin_costo_detalle.append(grupo)
    sin_costo_detalle.sort(
        key=lambda fila: (-fila["monto"], fila["producto"].casefold())
    )

    eventos_lista = []
    for grupo in eventos_agrupados.values():
        grupo["ventas"] = round(float(grupo["ventas"]), 2)
        eventos_lista.append(grupo)
    eventos_lista.sort(
        key=lambda fila: (
            fila["id_evento"] is None,
            str(fila["evento"]).casefold(),
        )
    )

    margen = None
    if ventas_con_costo and monto_con_costo > 0:
        margen = round(utilidad_estimada / monto_con_costo * 100, 2)

    return {
        "total_registros": total_registros,
        "con_datos": total_registros > 0,
        "ventas_totales": (
            0.0
            if total_registros == 0
            else round(monto_total, 2) if registros_con_total else None
        ),
        "registros_con_total": registros_con_total,
        "registros_sin_total": registros_sin_total,
        "cantidad_total": (
            0.0
            if total_registros == 0
            else round(cantidad_total, 4) if registros_con_cantidad else None
        ),
        "registros_con_cantidad": registros_con_cantidad,
        "registros_sin_cantidad": registros_sin_cantidad,
        "ventas_identificadas": ventas_identificadas,
        "ventas_pendientes": ventas_pendientes,
        "monto_pendiente": round(monto_pendiente, 2),
        "ventas_con_costo": ventas_con_costo,
        "monto_con_costo": (
            round(monto_con_costo, 2) if ventas_con_costo else None
        ),
        "costo_estimado": (
            round(costo_estimado, 2) if ventas_con_costo else None
        ),
        "utilidad_estimada": (
            round(utilidad_estimada, 2) if ventas_con_costo else None
        ),
        "margen_estimado": margen,
        "ventas_identificadas_sin_costo": ventas_identificadas_sin_costo,
        "monto_identificado_sin_costo": round(monto_identificado_sin_costo, 2),
        "por_categoria": categorias,
        "por_producto": productos_agrupados,
        "sin_costo": sin_costo_detalle,
        "eventos": eventos_lista,
        "truncado": bool(truncado),
    }


@cache_datos(ttl=60)
def _resumen(
    desde: Optional[str],
    hasta: Optional[str],
    id_evento: Optional[int],
) -> Dict[str, Any]:
    try:
        ventas = VentasFudoRepository().listar_para_rentabilidad(
            desde=desde,
            hasta=hasta,
            id_evento=id_evento,
            limite=LIMITE_RENTABILIDAD,
        )
        productos = listar_productos(solo_activos=False)
        eventos = listar_eventos(incluir_inactivos=True)
    except Exception as exc:
        raise como_error(exc) from exc

    return calcular_resumen_rentabilidad(
        ventas,
        productos,
        eventos,
        truncado=len(ventas) >= LIMITE_RENTABILIDAD,
    )


def resumen_rentabilidad(
    *,
    desde: Any = None,
    hasta: Any = None,
    id_evento: Optional[int] = None,
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Indicadores de rentabilidad estimada, exclusivos de administración."""
    exigir_admin(usuario)
    evento = _entero(id_evento) if id_evento not in (None, "", 0, "0") else None
    return _resumen(_fecha_texto(desde), _fecha_texto(hasta), evento)
