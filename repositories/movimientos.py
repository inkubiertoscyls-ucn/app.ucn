"""
Movimientos de inventario repository.
"""
from typing import List, Dict, Optional
from datetime import date
from .base import BaseRepository


class MovimientosRepository(BaseRepository):
    def __init__(self):
        super().__init__("hecho_inventario")

    def create_many(self, filas: List[Dict]) -> List[Dict]:
        """Inserta varias filas en una sola llamada.

        PostgREST ejecuta el INSERT del arreglo como una sola sentencia, por lo
        que si una fila falla no se guarda ninguna. Se usa para la importación
        de entradas y así evitar cargas parciales.
        """
        if not filas:
            return []
        response = (
            self.client.table(self.table_name).insert(list(filas)).execute()
        )
        return response.data or []

    def observaciones_con_marcador(self, patron: str) -> List[str]:
        """Observaciones que contienen un marcador de importación.

        PostgREST usa `*` como comodín en `like`; se conserva el prefijo para
        filtrar en la base y no traer todo el historial.
        """
        response = (
            self.client.table(self.table_name)
            .select("observacion")
            .like("observacion", patron)
            .execute()
        )
        return [
            str(fila.get("observacion") or "")
            for fila in (response.data or [])
            if fila.get("observacion")
        ]
    
    def get_by_producto(self, id_producto: int) -> List[Dict]:
        """Get movements by product."""
        return self.get_all({"id_producto": id_producto})
    
    def get_by_area(self, id_area: int) -> List[Dict]:
        """Get movements by area."""
        return self.get_all({"id_area": id_area})
    
    def get_by_fecha(self, id_fecha: int) -> List[Dict]:
        """Get movements by date."""
        return self.get_all({"id_fecha": id_fecha})
    
    def get_by_usuario(self, rut_usuario: str) -> List[Dict]:
        """Get movements by user."""
        return self.get_all({"rut_usuario": rut_usuario})
    
    def buscar_historial(self, id_producto: int = None, id_area: int = None,
                         id_tipo_movimiento: int = None, rut_usuario: str = None,
                         id_fecha_desde: int = None, id_fecha_hasta: int = None,
                         limite: int = None) -> List[Dict]:
        """Filtra movimientos y propaga errores.

        Es la versión estricta de `filtrar`: la capa de datos la usa para poder
        mostrar un error real en lugar de una lista vacía.
        """
        query = self.client.table(self.table_name).select("*")
        if id_producto:
            query = query.eq("id_producto", id_producto)
        if id_area:
            query = query.eq("id_area", id_area)
        if id_tipo_movimiento:
            query = query.eq("id_tipo_movimiento", id_tipo_movimiento)
        if rut_usuario:
            query = query.eq("rut_usuario", rut_usuario)
        if id_fecha_desde:
            query = query.gte("id_fecha", id_fecha_desde)
        if id_fecha_hasta:
            query = query.lte("id_fecha", id_fecha_hasta)
        query = query.order("fecha_hora_registro", desc=True)
        if limite:
            query = query.limit(int(limite))
        response = query.execute()
        return response.data or []

    def filtrar(self, id_producto: int = None, id_area: int = None, 
                id_tipo_movimiento: int = None, rut_usuario: str = None,
                id_fecha_desde: int = None, id_fecha_hasta: int = None) -> List[Dict]:
        """Filter movements."""
        try:
            return self.buscar_historial(
                id_producto=id_producto,
                id_area=id_area,
                id_tipo_movimiento=id_tipo_movimiento,
                rut_usuario=rut_usuario,
                id_fecha_desde=id_fecha_desde,
                id_fecha_hasta=id_fecha_hasta,
            )
        except Exception:
            return []

    def stock_agregado(self, tamano_pagina: int = 1000) -> List[Dict]:
        """Obtiene todos los movimientos necesarios para calcular stock.

        Recorre el resultado por páginas para no depender del límite de filas
        de PostgREST. Es una sola consulta lógica con el factor del tipo de
        movimiento, en lugar de consultar producto por producto.
        """
        tamano = max(1, int(tamano_pagina))
        filas: List[Dict] = []
        inicio = 0

        while True:
            response = (
                self.client.table(self.table_name)
                .select(
                    "id_producto, id_area, cantidad, "
                    "dim_tipo_movimiento(tipo_movimiento, factor_stock)"
                )
                .order("id_hecho_inventario", desc=False)
                .range(inicio, inicio + tamano - 1)
                .execute()
            )
            lote = response.data or []
            filas.extend(lote)
            if len(lote) < tamano:
                break
            inicio += tamano

        return filas
    
    def get_all_con_relaciones(self) -> List[Dict]:
        """Get all movements with related data."""
        try:
            response = self.client.table(self.table_name).select(
                "*, dim_producto(*), dim_area(*), dim_tipo_movimiento(*), dim_usuario(*), dim_proveedor(*), dim_evento(*), dim_fecha(*)"
            ).execute()
            return response.data or []
        except Exception:
            return []
    
    def get_stock_movimientos(self, id_producto: int, id_area: int = None) -> List[Dict]:
        """Get movements for stock calculation."""
        try:
            query = self.client.table(self.table_name).select(
                "cantidad, id_tipo_movimiento, dim_tipo_movimiento(factor_stock)"
            ).eq("id_producto", id_producto)
            if id_area:
                query = query.eq("id_area", id_area)
            response = query.execute()
            return response.data or []
        except Exception:
            return []
