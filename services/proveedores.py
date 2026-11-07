"""
Proveedores service - Business logic for suppliers.

El RUT es la clave primaria. Se normaliza al registrar y no se permite
cambiarlo después del alta para no romper las referencias de
`hecho_inventario.rut_proveedor`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.exceptions import DuplicateError, NotFoundError, ValidationError
from core.utils import normalizar_rut, validar_rut
from repositories.proveedores import ProveedoresRepository

CAMPOS_CREACION = (
    "rut_proveedor",
    "nombre_proveedor",
    "contacto_proveedor",
    "tipo_proveedor",
    "activo",
)
CAMPOS_EDICION = ("nombre_proveedor", "contacto_proveedor", "tipo_proveedor")


class ProveedoresService:
    def __init__(self):
        self.repo = ProveedoresRepository()

    def listar_proveedores(self, solo_activos: bool = False) -> List[Dict]:
        """Lista proveedores. Por defecto incluye inactivos para administración."""
        if solo_activos:
            return self.repo.get_activos()
        return self.repo.get_all()

    def consultar_proveedor(self, rut: str) -> Optional[Dict]:
        """Consulta por RUT normalizado, sin ocultar errores de conexión."""
        rut_normalizado = self._normalizar_rut(rut)
        return self.repo.get_by_rut_estricto(rut_normalizado)

    def registrar_proveedor(self, data: Dict) -> Dict:
        """Registra un proveedor con RUT válido y único."""
        if not isinstance(data, dict):
            raise ValidationError("Los datos del proveedor no son válidos")

        datos = self._normalizar_datos(data, crear=True)
        self._validar_proveedor(datos)

        if self.repo.existe_rut(datos["rut_proveedor"]):
            raise DuplicateError("Ya existe un proveedor con ese RUT")

        datos.setdefault("activo", True)
        return self.repo.create(datos)

    def modificar_proveedor(self, rut: str, data: Dict) -> Dict:
        """Modifica nombre, contacto y tipo. El RUT no se puede cambiar."""
        actual = self.consultar_proveedor(rut)
        if not actual:
            raise NotFoundError("Proveedor no encontrado")

        if not isinstance(data, dict):
            raise ValidationError("Los datos del proveedor no son válidos")
        if "rut_proveedor" in data:
            nuevo_rut = self._normalizar_rut(data["rut_proveedor"])
            if nuevo_rut != str(actual.get("rut_proveedor") or ""):
                raise ValidationError("El RUT del proveedor no se puede modificar")

        cambios = self._normalizar_datos(data, crear=False)
        if not cambios:
            raise ValidationError("No hay cambios para guardar")

        combinado = {**actual, **cambios}
        self._validar_proveedor(
            {
                **combinado,
                "rut_proveedor": str(actual.get("rut_proveedor") or ""),
            }
        )

        return self.repo.update(
            "rut_proveedor", str(actual["rut_proveedor"]), cambios
        )

    def activar_proveedor(self, rut: str) -> Dict:
        """Reactiva un proveedor sin borrar su historial."""
        actual = self.consultar_proveedor(rut)
        if not actual:
            raise NotFoundError("Proveedor no encontrado")
        if actual.get("activo"):
            return actual
        return self.repo.update(
            "rut_proveedor", str(actual["rut_proveedor"]), {"activo": True}
        )

    def desactivar_proveedor(self, rut: str) -> Dict:
        """Desactiva un proveedor sin borrar su historial."""
        actual = self.consultar_proveedor(rut)
        if not actual:
            raise NotFoundError("Proveedor no encontrado")
        if not actual.get("activo"):
            return actual
        return self.repo.deactivate("rut_proveedor", str(actual["rut_proveedor"]))

    def buscar_proveedores(self, termino: str) -> List[Dict]:
        """Busca por nombre, RUT, contacto o tipo."""
        texto = str(termino or "").strip()
        if len(texto) < 2:
            raise ValidationError("Término de búsqueda debe tener al menos 2 caracteres")
        return self.repo.buscar_estricto(texto)

    def _normalizar_datos(self, data: Dict, *, crear: bool) -> Dict:
        datos: Dict[str, Any] = {}
        campos = CAMPOS_CREACION if crear else CAMPOS_EDICION

        for campo in campos:
            if campo not in data:
                continue
            valor = data.get(campo)
            if campo in {"nombre_proveedor", "contacto_proveedor", "tipo_proveedor"}:
                valor = str(valor).strip() if valor is not None else ""
            elif campo == "rut_proveedor":
                valor = self._normalizar_rut(valor)
            elif campo == "activo":
                valor = bool(valor)
            datos[campo] = valor

        if crear:
            datos.setdefault("nombre_proveedor", "")
            datos.setdefault("contacto_proveedor", "")
            datos.setdefault("tipo_proveedor", "")
            datos.setdefault("activo", True)

        return datos

    def _normalizar_rut(self, rut: Any) -> str:
        try:
            return normalizar_rut(rut)
        except Exception as exc:
            raise ValidationError("El RUT del proveedor no es válido") from exc

    def _validar_proveedor(self, data: Dict) -> None:
        rut = str(data.get("rut_proveedor") or "").strip()
        if not rut:
            raise ValidationError("El RUT del proveedor es requerido")
        if len(rut) > 12 or not validar_rut(rut):
            raise ValidationError("El RUT del proveedor no es válido")

        nombre = str(data.get("nombre_proveedor") or "").strip()
        if len(nombre) < 2:
            raise ValidationError(
                "El nombre del proveedor debe tener al menos 2 caracteres"
            )
        if len(nombre) > 150:
            raise ValidationError("El nombre del proveedor no puede exceder 150 caracteres")

        contacto = str(data.get("contacto_proveedor") or "").strip()
        if len(contacto) > 150:
            raise ValidationError("El contacto no puede exceder 150 caracteres")

        tipo = str(data.get("tipo_proveedor") or "").strip()
        if len(tipo) > 100:
            raise ValidationError("El tipo de proveedor no puede exceder 100 caracteres")
