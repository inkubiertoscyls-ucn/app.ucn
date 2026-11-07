"""
Eventos service - Business logic for events and artists.

El artista es un campo del evento (`nombre_artista`), no una entidad separada.
Los duplicados exactos de nombre se advierten en la interfaz, pero no se
bloquean: puede haber ediciones del mismo evento con el mismo nombre.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from core.exceptions import NotFoundError, ValidationError
from repositories.eventos import EventosRepository

CAMPOS_EVENTO = (
    "nombre_evento",
    "nombre_artista",
    "tipo_evento",
    "costo_artista",
    "activo",
)
MAX_COSTO_ARTISTA = 99_999_999.99


class EventosService:
    def __init__(self):
        self.repo = EventosRepository()

    def listar_eventos(self, solo_activos: bool = False) -> List[Dict]:
        """Lista eventos. Por defecto incluye inactivos para administración."""
        if solo_activos:
            return self.repo.get_activos()
        return self.repo.get_all()

    def consultar_evento(self, id_evento: int) -> Optional[Dict]:
        """Consulta un evento por ID sin ocultar errores de conexión."""
        try:
            identificador = int(id_evento)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El identificador del evento no es válido") from exc
        if identificador <= 0:
            raise ValidationError("El identificador del evento no es válido")
        return self.repo.get_by_id_estricto(identificador)

    def registrar_evento(self, data: Dict) -> Dict:
        """Registra un evento. No crea ventas, movimientos ni relaciones."""
        datos = self._normalizar_datos(data, crear=True)
        self._validar_evento(datos)
        datos.setdefault("activo", True)
        return self.repo.create(datos)

    def modificar_evento(self, id_evento: int, data: Dict) -> Dict:
        """Modifica un evento sin tocar ventas ni movimientos históricos."""
        evento = self.consultar_evento(id_evento)
        if not evento:
            raise NotFoundError("Evento no encontrado")

        cambios = self._normalizar_datos(data, crear=False)
        if not cambios:
            raise ValidationError("No hay cambios para guardar")

        combinado = {**evento, **cambios}
        self._validar_evento(combinado)

        return self.repo.update("id_evento", int(evento["id_evento"]), cambios)

    def activar_evento(self, id_evento: int) -> Dict:
        """Reactiva un evento sin borrar su historial."""
        evento = self.consultar_evento(id_evento)
        if not evento:
            raise NotFoundError("Evento no encontrado")
        if evento.get("activo"):
            return evento
        return self.repo.update(
            "id_evento", int(evento["id_evento"]), {"activo": True}
        )

    def desactivar_evento(self, id_evento: int) -> Dict:
        """Desactiva un evento conservando su nombre histórico."""
        evento = self.consultar_evento(id_evento)
        if not evento:
            raise NotFoundError("Evento no encontrado")
        if not evento.get("activo"):
            return evento
        return self.repo.deactivate("id_evento", int(evento["id_evento"]))

    def buscar_eventos(self, termino: str) -> List[Dict]:
        """Busca por nombre de evento, artista o tipo."""
        texto = str(termino or "").strip()
        if len(texto) < 2:
            raise ValidationError("Término de búsqueda debe tener al menos 2 caracteres")
        return self.repo.buscar_estricto(texto)

    def fechas_actividad(self) -> Dict[int, Dict[str, str]]:
        """Fechas derivadas de ventas y movimientos ya vinculados."""
        return self.repo.fechas_actividad()

    def _normalizar_datos(self, data: Dict, *, crear: bool) -> Dict:
        if not isinstance(data, dict):
            raise ValidationError("Los datos del evento no son válidos")

        datos: Dict[str, Any] = {}
        for campo in CAMPOS_EVENTO:
            if campo not in data:
                continue
            valor = data.get(campo)
            if campo in {"nombre_evento", "nombre_artista", "tipo_evento"}:
                valor = str(valor).strip() if valor is not None else ""
            elif campo == "costo_artista":
                valor = self._numero_no_negativo(valor, campo)
            elif campo == "activo":
                valor = bool(valor)
            datos[campo] = valor

        if crear:
            datos.setdefault("nombre_evento", "")
            datos.setdefault("nombre_artista", "")
            datos.setdefault("tipo_evento", "")
            datos.setdefault("costo_artista", 0.0)
            datos.setdefault("activo", True)

        return datos

    def _numero_no_negativo(self, valor: Any, campo: str) -> float:
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"El campo {campo} debe ser un número") from exc
        if not math.isfinite(numero) or numero < 0:
            raise ValidationError(f"El campo {campo} no puede ser negativo")
        return numero

    def _validar_evento(self, data: Dict) -> None:
        nombre = str(data.get("nombre_evento") or "").strip()
        if not nombre:
            raise ValidationError("El nombre del evento es requerido")
        if len(nombre) < 2:
            raise ValidationError(
                "El nombre del evento debe tener al menos 2 caracteres"
            )
        if len(nombre) > 150:
            raise ValidationError(
                "El nombre del evento no puede exceder 150 caracteres"
            )

        artista = str(data.get("nombre_artista") or "").strip()
        if len(artista) > 150:
            raise ValidationError(
                "El nombre del artista no puede exceder 150 caracteres"
            )

        tipo = str(data.get("tipo_evento") or "").strip()
        if not tipo:
            raise ValidationError("El tipo de evento es requerido")
        if len(tipo) > 50:
            raise ValidationError(
                "El tipo de evento no puede exceder 50 caracteres"
            )

        costo = self._numero_no_negativo(
            data.get("costo_artista", 0), "costo_artista"
        )
        if costo > MAX_COSTO_ARTISTA:
            raise ValidationError("El costo del artista excede el máximo permitido")
