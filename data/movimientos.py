"""Registro e historial de movimientos de inventario.

La escritura se delega en `InventarioService` y el stock se consulta con el
mismo read model que el resto del frontend (`data.inventario`). No se modifica
el esquema ni se duplica la fórmula de stock.
"""
from __future__ import annotations

import math
import time
from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from core.importacion import quitar_marcador
from data.cache import cache_datos, limpiar_cache
from data.catalogos import area_id, listar_areas, listar_tipos_movimiento
from data.errors import (
    NO_ENCONTRADO,
    PERMISOS,
    VALIDACION,
    ErrorDatos,
    como_error,
)
from data.inventario import historial, stock_actual
from data.permisos import ADMINISTRADOR, area_operario, exigir_sesion
from data.productos import listar_productos
from repositories.usuarios import UsuariosRepository
from services.inventario import InventarioService

# Ventana en segundos para ignorar un doble envío idéntico.
VENTANA_DUPLICADOS = 4.0
CLAVE_ULTIMO_MOVIMIENTO = "_ink_ultimo_movimiento"

_METODOS_POR_TIPO = {
    "entrada": "registrar_entrada",
    "salida": "registrar_salida",
    "merma": "registrar_merma",
    "ajuste positivo": "registrar_ajuste_positivo",
    "ajuste negativo": "registrar_ajuste_negativo",
}


def _normalizar(texto: Any) -> str:
    return " ".join(str(texto or "").strip().casefold().split())


def _numero_texto(valor: Any) -> str:
    """Formato simple para mensajes de la capa de datos (sin depender de ui)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "0"
    return f"{numero:.2f}".rstrip("0").rstrip(".") if not numero.is_integer() else f"{numero:.0f}"


def _cantidad_entera(valor: Any) -> int:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErrorDatos(
            "La cantidad debe ser un número entero mayor que cero.",
            tipo=VALIDACION,
        )
    if not math.isfinite(numero) or not numero.is_integer():
        raise ErrorDatos(
            "La cantidad debe ser un número entero mayor que cero.",
            tipo=VALIDACION,
        )
    entero = int(numero)
    if entero <= 0:
        raise ErrorDatos(
            "La cantidad debe ser mayor que cero.",
            tipo=VALIDACION,
        )
    return entero


def _costo_unitario(producto: Dict[str, Any], valor: Any) -> float:
    """Costo obligatorio del movimiento: usa `costo_base` como respaldo."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        valor = producto.get("costo_base")
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        valor = 0
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErrorDatos(
            "El costo unitario debe ser un número mayor o igual a cero.",
            tipo=VALIDACION,
        )
    if not math.isfinite(numero) or numero < 0:
        raise ErrorDatos(
            "El costo unitario debe ser un número mayor o igual a cero.",
            tipo=VALIDACION,
        )
    return numero


def _area_de_registro(
    id_area: Optional[int],
    actual: Dict[str, Any],
    areas: List[Dict[str, Any]],
) -> tuple[int, str]:
    """Resuelve y valida el área del movimiento según el rol."""
    mapa = {
        int(area.get("id_area")): str(area.get("nombre_area") or "Sin nombre")
        for area in areas
        if area.get("id_area") is not None
    }

    if actual.get("rol") == ADMINISTRADOR:
        if id_area is None:
            raise ErrorDatos(
                "Selecciona un área para registrar el movimiento.",
                tipo=VALIDACION,
            )
        try:
            elegida = int(id_area)
        except (TypeError, ValueError):
            elegida = -1
        if elegida not in mapa:
            raise ErrorDatos(
                "El área seleccionada no está disponible.",
                tipo=NO_ENCONTRADO,
            )
        return elegida, mapa[elegida]

    nombre_propio = area_operario(actual)
    propio = area_id(nombre_propio, areas)
    if propio is None:
        raise ErrorDatos(
            "Tu cuenta no tiene un área válida asignada. Contacta al administrador.",
            tipo=PERMISOS,
        )

    if id_area is not None:
        try:
            enviada = int(id_area)
        except (TypeError, ValueError):
            enviada = -1
        if enviada != propio:
            raise AuthorizationError(
                "No puedes registrar movimientos en un área distinta a la asignada."
            )

    return propio, mapa.get(propio, nombre_propio)


def _buscar_producto(
    id_producto: int,
    productos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    for producto in productos:
        try:
            if int(producto.get("id_producto")) == id_producto:
                return producto
        except (TypeError, ValueError):
            continue
    raise ErrorDatos(
        "El producto seleccionado ya no está disponible.",
        tipo=NO_ENCONTRADO,
    )


def _buscar_tipo(
    id_tipo_movimiento: int,
    tipos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    for tipo in tipos:
        try:
            if int(tipo.get("id_tipo_movimiento")) == id_tipo_movimiento:
                return tipo
        except (TypeError, ValueError):
            continue
    raise ErrorDatos(
        "El tipo de movimiento seleccionado no está activo.",
        tipo=VALIDACION,
    )


def _estado_sesion():
    try:
        return st.session_state
    except Exception:
        return None


def _revisar_duplicado(firma: tuple) -> None:
    """Bloquea un segundo envío idéntico inmediato (doble clic o reintento)."""
    estado = _estado_sesion()
    if estado is None:
        return
    ultimo = estado.get(CLAVE_ULTIMO_MOVIMIENTO)
    if not isinstance(ultimo, dict) or ultimo.get("firma") != firma:
        return
    try:
        transcurrido = time.monotonic() - float(ultimo.get("registrado_en"))
    except (TypeError, ValueError):
        return
    if transcurrido < VENTANA_DUPLICADOS:
        raise ErrorDatos(
            "Este movimiento ya fue registrado. Espera unos segundos antes de "
            "volver a intentarlo.",
            tipo=VALIDACION,
        )


def _recordar_movimiento(firma: tuple) -> None:
    estado = _estado_sesion()
    if estado is None:
        return
    estado[CLAVE_ULTIMO_MOVIMIENTO] = {
        "firma": firma,
        "registrado_en": time.monotonic(),
    }


def registrar_movimiento(
    *,
    id_producto: int,
    id_tipo_movimiento: int,
    cantidad: Any,
    id_area: Optional[int] = None,
    costo_unitario: Any = None,
    observacion: str = "",
    usuario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Registra un movimiento real usando `InventarioService`.

    Valida rol, área, producto, tipo y stock antes de escribir. Un operario
    queda siempre limitado a su área; el administrador debe elegir un área.
    """
    actual = exigir_sesion(usuario)
    rut = str(actual.get("rut_usuario") or "").strip()
    if not rut:
        raise AuthorizationError(
            "Tu sesión no tiene un usuario válido. Vuelve a iniciar sesión."
        )

    cantidad_entera = _cantidad_entera(cantidad)

    try:
        productos = listar_productos(solo_activos=True)
        tipos = listar_tipos_movimiento()
        areas = listar_areas()
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc

    try:
        id_producto_int = int(id_producto)
    except (TypeError, ValueError):
        raise ErrorDatos(
            "Selecciona un producto para registrar el movimiento.",
            tipo=VALIDACION,
        )
    try:
        id_tipo_int = int(id_tipo_movimiento)
    except (TypeError, ValueError):
        raise ErrorDatos(
            "Selecciona un tipo de movimiento.",
            tipo=VALIDACION,
        )

    producto = _buscar_producto(id_producto_int, productos)
    tipo = _buscar_tipo(id_tipo_int, tipos)
    area, nombre_area = _area_de_registro(id_area, actual, areas)
    costo = _costo_unitario(producto, costo_unitario)

    nombre_tipo = str(tipo.get("tipo_movimiento") or "").strip()
    metodo = _METODOS_POR_TIPO.get(_normalizar(nombre_tipo))
    if metodo is None:
        raise ErrorDatos(
            f"El tipo de movimiento “{nombre_tipo}” no está soportado por la "
            "pantalla de movimientos.",
            tipo=VALIDACION,
        )

    try:
        factor = int(tipo.get("factor_stock"))
    except (TypeError, ValueError):
        factor = 0
    if factor not in (1, -1):
        raise ErrorDatos(
            "El tipo de movimiento no tiene un factor de stock válido.",
            tipo=VALIDACION,
        )

    unidad = str(producto.get("unidad_medida") or "").strip()
    stock = float(stock_actual(id_producto_int, area, usuario=actual))
    if factor < 0 and stock - cantidad_entera < 0:
        unidad_texto = f" {unidad}" if unidad else ""
        raise ErrorDatos(
            "Stock insuficiente en "
            f"{nombre_area}: disponible {_numero_texto(stock)}{unidad_texto}, "
            f"solicitado {_numero_texto(cantidad_entera)}{unidad_texto}. "
            "Ajusta la cantidad o registra primero una entrada.",
            tipo=VALIDACION,
        )

    firma = (
        rut,
        id_producto_int,
        area,
        id_tipo_int,
        cantidad_entera,
        costo,
        _normalizar(observacion),
    )
    _revisar_duplicado(firma)

    datos = {
        "id_producto": id_producto_int,
        "id_area": area,
        "id_tipo_movimiento": id_tipo_int,
        "rut_usuario": rut,
        "cantidad": cantidad_entera,
        "costo_unitario": costo,
    }
    observacion_limpia = str(observacion or "").strip()
    if observacion_limpia:
        datos["observacion"] = observacion_limpia

    try:
        creado = getattr(InventarioService(), metodo)(datos)
    except ErrorDatos:
        raise
    except Exception as exc:
        raise como_error(exc) from exc

    limpiar_cache()
    _recordar_movimiento(firma)

    nombre_producto = str(producto.get("nombre_producto") or "Producto").strip()
    return {
        "movimiento": creado,
        "id_producto": id_producto_int,
        "producto": nombre_producto,
        "unidad": unidad,
        "tipo": nombre_tipo,
        "factor": factor,
        "id_area": area,
        "area": nombre_area,
        "cantidad": cantidad_entera,
        "costo_unitario": costo,
        "stock_anterior": stock,
        "stock_nuevo": stock + (factor * cantidad_entera),
        "fecha": date.today(),
    }


@cache_datos(ttl=300)
def _nombres_usuarios() -> Dict[str, str]:
    try:
        filas = UsuariosRepository().nombres_por_rut()
    except Exception as exc:
        raise como_error(exc) from exc
    return {
        str(fila.get("rut_usuario")): str(fila.get("nombre_usuario") or "").strip()
        for fila in filas
        if fila.get("rut_usuario") is not None
    }


def _mapas_historial() -> tuple[
    Dict[int, Dict[str, Any]],
    Dict[int, str],
    Dict[int, Dict[str, Any]],
    Dict[str, str],
]:
    productos = {
        int(producto.get("id_producto")): producto
        for producto in listar_productos(solo_activos=False)
        if producto.get("id_producto") is not None
    }
    areas = {
        int(area.get("id_area")): str(area.get("nombre_area") or "Sin área")
        for area in listar_areas(incluir_inactivas=True)
        if area.get("id_area") is not None
    }
    tipos = {
        int(tipo.get("id_tipo_movimiento")): tipo
        for tipo in listar_tipos_movimiento(incluir_inactivos=True)
        if tipo.get("id_tipo_movimiento") is not None
    }
    usuarios = _nombres_usuarios()
    return productos, areas, tipos, usuarios


def _coincide_texto(fila: Dict[str, Any], termino: str) -> bool:
    if not termino:
        return True
    campos = (
        fila.get("producto"),
        fila.get("categoria"),
        fila.get("area"),
        fila.get("tipo"),
        fila.get("usuario"),
        fila.get("rut_usuario"),
        fila.get("observacion"),
    )
    return any(termino in str(campo or "").casefold() for campo in campos)


def historial_movimientos(
    *,
    desde: Any = None,
    hasta: Any = None,
    id_producto: Optional[int] = None,
    id_tipo_movimiento: Optional[int] = None,
    id_area: Optional[int] = None,
    texto: str = "",
    limite: int = 300,
    usuario: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Historial enriquecido con nombres, signo y observaciones.

    El filtro de área del operario se aplica en `data.inventario.historial`,
    antes de cualquier filtro de esta función.
    """
    actual = exigir_sesion(usuario)

    producto_filtro = None
    if id_producto not in (None, "", 0, "0"):
        try:
            producto_filtro = int(id_producto)
        except (TypeError, ValueError):
            producto_filtro = None

    tipo_filtro = None
    if id_tipo_movimiento not in (None, "", 0, "0"):
        try:
            tipo_filtro = int(id_tipo_movimiento)
        except (TypeError, ValueError):
            tipo_filtro = None

    area_filtro = None
    if id_area not in (None, "", 0, "0"):
        try:
            area_filtro = int(id_area)
        except (TypeError, ValueError):
            area_filtro = None

    filas = historial(
        id_producto=producto_filtro,
        id_tipo_movimiento=tipo_filtro,
        id_area=area_filtro,
        desde=desde,
        hasta=hasta,
        limite=limite,
        usuario=actual,
    )

    productos, areas, tipos, usuarios = _mapas_historial()
    termino = str(texto or "").strip().casefold()
    resultado: List[Dict[str, Any]] = []

    for movimiento in filas:
        try:
            id_prod = int(movimiento.get("id_producto"))
        except (TypeError, ValueError):
            id_prod = 0
        try:
            id_ar = int(movimiento.get("id_area"))
        except (TypeError, ValueError):
            id_ar = 0
        try:
            id_tipo = int(movimiento.get("id_tipo_movimiento"))
        except (TypeError, ValueError):
            id_tipo = 0

        producto = productos.get(id_prod) or {}
        tipo = tipos.get(id_tipo) or {}
        factor = tipo.get("factor_stock")
        try:
            factor_int = int(factor)
        except (TypeError, ValueError):
            factor_int = 0
        try:
            cantidad = float(movimiento.get("cantidad") or 0)
        except (TypeError, ValueError):
            cantidad = 0.0
        try:
            costo_unitario = float(movimiento.get("costo_unitario") or 0)
        except (TypeError, ValueError):
            costo_unitario = 0.0

        rut = str(movimiento.get("rut_usuario") or "").strip()
        usuario_nombre = usuarios.get(rut) or rut or "Sin usuario"
        nombre_producto = str(
            producto.get("nombre_producto") or "Producto no disponible"
        ).strip()
        fila = {
            "id": movimiento.get("id_hecho_inventario"),
            "fecha_hora": movimiento.get("fecha_hora_registro"),
            "id_producto": id_prod,
            "producto": nombre_producto,
            "categoria": str(producto.get("categoria") or "Sin categoría"),
            "unidad": str(producto.get("unidad_medida") or ""),
            "id_area": id_ar,
            "area": areas.get(id_ar, "Sin área"),
            "id_tipo_movimiento": id_tipo,
            "tipo": str(tipo.get("tipo_movimiento") or "Sin tipo"),
            "factor": factor_int,
            "cantidad": abs(cantidad),
            "cantidad_firmada": cantidad * factor_int,
            "costo_unitario": costo_unitario,
            "costo_total": costo_unitario * abs(cantidad),
            "observacion": quitar_marcador(movimiento.get("observacion")),
            "rut_usuario": rut,
            "usuario": usuario_nombre,
        }

        if not _coincide_texto(fila, termino):
            continue
        resultado.append(fila)

    return resultado
