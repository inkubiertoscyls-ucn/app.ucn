"""Pruebas de la grilla de métricas reutilizable."""
from __future__ import annotations

from ui.layout import metric_grid


def _items(cantidad):
    return [
        {"label": f"Métrica {indice}", "value": indice, "tone": "default"}
        for indice in range(1, cantidad + 1)
    ]


def _capturar(monkeypatch):
    capturado = {}

    def falso_markdown(html, **kwargs):
        capturado["html"] = html

    monkeypatch.setattr("ui.layout.st.markdown", falso_markdown)
    return capturado


def test_metric_grid_usa_el_total_si_no_se_indican_columnas(monkeypatch):
    capturado = _capturar(monkeypatch)

    metric_grid(_items(4))

    assert "ink-metrics--4" in capturado["html"]
    assert "Métrica 4" in capturado["html"]


def test_metric_grid_acepta_columns_explicito(monkeypatch):
    capturado = _capturar(monkeypatch)

    metric_grid(_items(4), columns=4)

    assert "ink-metrics--4" in capturado["html"]


def test_metric_grid_de_tres_columnas(monkeypatch):
    capturado = _capturar(monkeypatch)

    metric_grid(_items(3), columns=3)

    assert "ink-metrics--3" in capturado["html"]
