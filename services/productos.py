"""
Productos service - Business logic for products.

El catálogo de productos es global: el stock no vive en `dim_producto`, sino
que se calcula desde `hecho_inventario`. Registrar o editar un producto nunca
crea movimientos ni stock artificial.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from core.exceptions import DuplicateError, NotFoundError, ValidationError
from repositories.productos import ProductosRepository

CAMPOS_PRODUCTO = (
    "nombre_producto",
    "categoria",
    "unidad_medida",
    "costo_base",
    "stock_minimo",
    "stock_maximo",
    "activo",
)
MAX_COSTO_BASE = 99_999_999.99


class ProductosService:
    def __init__(self):
        self.repo = ProductosRepository()

    def listar_productos(self, solo_activos: bool = True) -> List[Dict]:
        """List products."""
        if solo_activos:
            return self.repo.get_activos()
        return self.repo.get_all()

    def consultar_producto(self, id_producto: int) -> Optional[Dict]:
        """Get product by ID without hiding connection errors."""
        try:
            identificador = int(id_producto)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El identificador del producto no es válido") from exc
        if identificador <= 0:
            raise ValidationError("El identificador del producto no es válido")
        return self.repo.get_by_id_estricto(identificador)

    def registrar_producto(self, data: Dict) -> Dict:
        """Register new product. Never writes inventory movements."""
        datos = self._normalizar_datos(data, crear=True)
        self._validar_producto(datos)
        if self.repo.existe_nombre(datos["nombre_producto"]):
            raise DuplicateError("Ya existe un producto con ese nombre")
        datos.setdefault("activo", True)
        return self.repo.create(datos)

    def modificar_producto(self, id_producto: int, data: Dict) -> Dict:
        """Modify product data without touching stock or movements."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")

        cambios = self._normalizar_datos(data, crear=False)
        if not cambios:
            raise ValidationError("No hay cambios para guardar")

        combinado = {**producto, **cambios}
        self._validar_producto(combinado)

        if "nombre_producto" in cambios:
            if self.repo.existe_nombre(
                cambios["nombre_producto"],
                exclude_id=int(producto["id_producto"]),
            ):
                raise DuplicateError("Ya existe un producto con ese nombre")

        return self.repo.update("id_producto", int(producto["id_producto"]), cambios)

    def activar_producto(self, id_producto: int) -> Dict:
        """Reactivate a product without changing its history."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")
        if producto.get("activo"):
            return producto
        return self.repo.update(
            "id_producto", int(producto["id_producto"]), {"activo": True}
        )

    def desactivar_producto(self, id_producto: int) -> Dict:
        """Deactivate product without deleting history."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")
        if not producto.get("activo"):
            return producto
        return self.repo.deactivate("id_producto", int(producto["id_producto"]))

    def consultar_stock_min_max(self, id_producto: int) -> Dict:
        """Get min and max stock configured."""
        producto = self.consultar_producto(id_producto)
        if not producto:
            raise NotFoundError("Producto no encontrado")
        return {
            "id_producto": int(producto["id_producto"]),
            "stock_minimo": producto.get("stock_minimo", 0),
            "stock_maximo": producto.get("stock_maximo", 0),
        }

    def buscar_productos(self, termino: str) -> List[Dict]:
        """Search products by name or category."""
        if not termino or len(termino.strip()) < 2:
            raise ValidationError("Término de búsqueda debe tener al menos 2 caracteres")
        return self.repo.buscar(termino.strip())

    def _normalizar_datos(self, data: Dict, *, crear: bool) -> Dict:
        """Conserva solo campos reales y normaliza textos y números."""
        if not isinstance(data, dict):
            raise ValidationError("Los datos del producto no son válidos")

        datos: Dict[str, Any] = {}
        for campo in CAMPOS_PRODUCTO:
            if campo not in data:
                continue
            valor = data.get(campo)
            if campo in {"nombre_producto", "categoria", "unidad_medida"}:
                valor = str(valor).strip() if valor is not None else ""
            elif campo in {"costo_base", "stock_minimo", "stock_maximo"}:
                valor = self._numero_no_negativo(valor, campo)
            elif campo == "activo":
                valor = bool(valor)
            datos[campo] = valor

        if crear:
            datos.setdefault("nombre_producto", "")
            datos.setdefault("categoria", "")
            datos.setdefault("unidad_medida", "")
            datos.setdefault("costo_base", 0.0)
            datos.setdefault("stock_minimo", 0.0)
            datos.setdefault("stock_maximo", 0.0)
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

    def _validar_producto(self, data: Dict) -> None:
        """Validate the complete product, including merged edit values."""
        nombre = str(data.get("nombre_producto") or "").strip()
        if not nombre:
            raise ValidationError("El nombre del producto es requerido")
        self._validar_nombre(nombre)

        categoria = str(data.get("categoria") or "").strip()
        if len(categoria) > 100:
            raise ValidationError("La categoría no puede exceder 100 caracteres")

        unidad = str(data.get("unidad_medida") or "").strip()
        if not unidad:
            raise ValidationError("La unidad de medida es requerida")
        if len(unidad) > 50:
            raise ValidationError("La unidad de medida no puede exceder 50 caracteres")

        costo = self._numero_no_negativo(data.get("costo_base", 0), "costo_base")
        if costo > MAX_COSTO_BASE:
            raise ValidationError("El costo base excede el máximo permitido")

        minimo = self._numero_no_negativo(data.get("stock_minimo", 0), "stock_minimo")
        maximo = self._numero_no_negativo(data.get("stock_maximo", 0), "stock_maximo")
        if maximo > 0 and maximo < minimo:
            raise ValidationError(
                "El stock máximo debe ser mayor o igual que el stock mínimo"
            )

    def _validar_nombre(self, nombre: str) -> None:
        """Validate product name."""
        nombre = str(nombre).strip()
        if len(nombre) < 2:
            raise ValidationError("El nombre del producto debe tener al menos 2 caracteres")
        if len(nombre) > 150:
            raise ValidationError("El nombre del producto no puede exceder 150 caracteres")
