"""Pruebas de las lecturas de ventas FUDO."""
import pytest

from core.exceptions import AuthorizationError
from data.ventas import listar_ventas_recientes

ADMIN = {
    "rut_usuario": "12345678-9",
    "rol": "Administrador",
    "area_asignada": "Todas",
    "activo": True,
}
OPERARIO = {
    "rut_usuario": "11111111-1",
    "rol": "Operario",
    "area_asignada": "Barra",
    "activo": True,
}


class FakeVentasRepo:
    def __init__(self):
        self.limite = None

    def listar_recientes(self, limite=50):
        self.limite = limite
        return [{"id_venta_fudo": 1, "total_venta": 1000}]


def test_admin_puede_listar_ventas(monkeypatch):
    repo = FakeVentasRepo()
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: repo)

    ventas = listar_ventas_recientes(usuario=ADMIN)

    assert ventas == [{"id_venta_fudo": 1, "total_venta": 1000}]


def test_limite_se_acota(monkeypatch):
    repo = FakeVentasRepo()
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: repo)

    listar_ventas_recientes(9999, usuario=ADMIN)

    assert repo.limite == 200


def test_operario_no_puede_ver_ventas(monkeypatch):
    monkeypatch.setattr("data.ventas.VentasFudoRepository", lambda: FakeVentasRepo())

    with pytest.raises(AuthorizationError):
        listar_ventas_recientes(usuario=OPERARIO)
