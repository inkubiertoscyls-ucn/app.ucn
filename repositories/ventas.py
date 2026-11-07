"""Repositorio de ventas FUDO.

Los listados excluyen `datos_raw` de forma deliberada: es un campo pesado y
solo se conserva como respaldo del registro original. La vinculación con
productos se actualiza de forma puntual y nunca modifica fechas, montos ni el
nombre original informado por FUDO.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .base import BaseRepository


def _fecha_texto(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    return texto[:10] if texto else None


class VentasFudoRepository(BaseRepository):
    CAMPOS_LISTADO = (
        "id_venta_fudo, fecha_venta, id_evento, origen_archivo, "
        "total_venta, cantidad_total, producto_identificado, "
        "id_producto_relacionado, importado_por, fecha_importacion"
    )
    CAMPOS_RENTABILIDAD = (
        "id_venta_fudo, fecha_venta, id_evento, total_venta, "
        "cantidad_total, producto_identificado, id_producto_relacionado"
    )

    def __init__(self):
        super().__init__("hecho_venta_fudo")

    def _consulta_listado(
        self,
        *,
        desde: Any = None,
        hasta: Any = None,
        solo_pendientes: bool = False,
        texto: str = "",
        id_evento: Optional[int] = None,
    ):
        query = self.client.table(self.table_name).select(self.CAMPOS_LISTADO)
        desde_texto = _fecha_texto(desde)
        hasta_texto = _fecha_texto(hasta)
        if desde_texto:
            query = query.gte("fecha_venta", desde_texto)
        if hasta_texto:
            query = query.lte("fecha_venta", hasta_texto)
        if solo_pendientes:
            query = query.is_("id_producto_relacionado", "null")
        if id_evento is not None:
            query = query.eq("id_evento", int(id_evento))
        termino = str(texto or "").strip()
        if termino:
            query = query.ilike("producto_identificado", f"%{termino}%")
        return query.order("fecha_venta", desc=True).order(
            "id_venta_fudo", desc=True
        )

    def listar(
        self,
        *,
        desde: Any = None,
        hasta: Any = None,
        solo_pendientes: bool = False,
        texto: str = "",
        id_evento: Optional[int] = None,
        limite: int = 100,
    ) -> List[Dict]:
        """Lista ventas con filtros, sin `datos_raw`."""
        limite_seguro = max(1, min(int(limite), 1000))
        response = (
            self._consulta_listado(
                desde=desde,
                hasta=hasta,
                solo_pendientes=solo_pendientes,
                texto=texto,
                id_evento=id_evento,
            )
            .limit(limite_seguro)
            .execute()
        )
        return response.data or []

    def listar_recientes(self, limite: int = 50) -> List[Dict]:
        """Compatibilidad: ventas más recientes por fecha de importación."""
        response = (
            self.client.table(self.table_name)
            .select(self.CAMPOS_LISTADO)
            .order("fecha_importacion", desc=True)
            .limit(max(1, int(limite)))
            .execute()
        )
        return response.data or []

    def listar_pendientes(self, limite: int = 200) -> List[Dict]:
        """Ventas sin producto vinculado."""
        return self.listar(solo_pendientes=True, limite=limite)

    def hashes_existentes(self) -> set[str]:
        """Todos los hashes ya almacenados, para deduplicar en aplicación."""
        hashes: set[str] = set()
        tamano = 1000
        inicio = 0
        while True:
            response = (
                self.client.table(self.table_name)
                .select("hash_registro")
                .order("id_venta_fudo", desc=False)
                .range(inicio, inicio + tamano - 1)
                .execute()
            )
            lote = response.data or []
            for fila in lote:
                valor = fila.get("hash_registro")
                if valor:
                    hashes.add(str(valor))
            if len(lote) < tamano:
                break
            inicio += tamano
        return hashes

    def actualizar_vinculacion(
        self,
        id_venta_fudo: int,
        id_producto: Optional[int],
    ) -> List[Dict]:
        """Actualiza solo la relación con el producto.

        Devuelve las filas modificadas. El nombre original de FUDO, la fecha,
        el monto y `datos_raw` permanecen intactos.
        """
        response = (
            self.client.table(self.table_name)
            .update({"id_producto_relacionado": id_producto})
            .eq("id_venta_fudo", int(id_venta_fudo))
            .execute()
        )
        return response.data or []

    def ids_por_producto_identificado(self, producto_identificado: str) -> List[int]:
        """Ids de ventas pendientes con el nombre original indicado."""
        response = (
            self.client.table(self.table_name)
            .select("id_venta_fudo")
            .eq("producto_identificado", str(producto_identificado))
            .is_("id_producto_relacionado", "null")
            .execute()
        )
        ids: List[int] = []
        for fila in response.data or []:
            try:
                ids.append(int(fila.get("id_venta_fudo")))
            except (TypeError, ValueError):
                continue
        return ids

    def vincular_por_producto_identificado(
        self,
        producto_identificado: str,
        id_producto: int,
    ) -> List[int]:
        """Vincula todas las ventas pendientes con ese nombre original.

        Solo modifica `id_producto_relacionado`; no toca el registro original.
        """
        ids = self.ids_por_producto_identificado(producto_identificado)
        if not ids:
            return []

        # Se actualiza en lotes para no exceder el largo de la URL de PostgREST
        # cuando un nombre de FUDO acumula muchas ventas pendientes.
        tamano_lote = 100
        for inicio in range(0, len(ids), tamano_lote):
            lote = ids[inicio : inicio + tamano_lote]
            self.client.table(self.table_name).update(
                {"id_producto_relacionado": int(id_producto)}
            ).in_("id_venta_fudo", lote).execute()
        return ids

    def listar_para_rentabilidad(
        self,
        *,
        desde: Any = None,
        hasta: Any = None,
        id_evento: Optional[int] = None,
        limite: int = 10000,
    ) -> List[Dict]:
        """Ventas con los campos necesarios para el cálculo de rentabilidad.

        Recorre el resultado por páginas para no depender del límite de filas
        de PostgREST. No incluye `datos_raw`.
        """
        limite_seguro = max(1, min(int(limite), 50000))
        tamano = 1000
        inicio = 0
        filas: List[Dict] = []

        while len(filas) < limite_seguro:
            query = self.client.table(self.table_name).select(
                self.CAMPOS_RENTABILIDAD
            )
            desde_texto = _fecha_texto(desde)
            hasta_texto = _fecha_texto(hasta)
            if desde_texto:
                query = query.gte("fecha_venta", desde_texto)
            if hasta_texto:
                query = query.lte("fecha_venta", hasta_texto)
            if id_evento is not None:
                query = query.eq("id_evento", int(id_evento))
            response = (
                query.order("fecha_venta", desc=False)
                .order("id_venta_fudo", desc=False)
                .range(inicio, inicio + tamano - 1)
                .execute()
            )
            lote = response.data or []
            filas.extend(lote)
            if len(lote) < tamano:
                break
            inicio += tamano

        return filas[:limite_seguro]
