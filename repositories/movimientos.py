"""
Movimientos de inventario repository.
"""
from typing import List, Dict, Optional
from datetime import date
from .base import BaseRepository


class MovimientosRepository(BaseRepository):
    def __init__(self):
        super().__init__("hecho_inventario")
    
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
    
    def filtrar(self, id_producto: int = None, id_area: int = None, 
                id_tipo_movimiento: int = None, rut_usuario: str = None,
                id_fecha_desde: int = None, id_fecha_hasta: int = None) -> List[Dict]:
        """Filter movements."""
        try:
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
            response = query.execute()
            return response.data or []
        except Exception:
            return []
    
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
