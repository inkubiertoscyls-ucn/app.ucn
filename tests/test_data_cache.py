"""Pruebas del comportamiento de la caché de lecturas."""
from data.cache import cache_datos

LLAMADAS = {"n": 0}


@cache_datos(ttl=60)
def _lectura_cache(valor):
    LLAMADAS["n"] += 1
    return valor * 2


def test_cache_desactivada_consulta_siempre(monkeypatch):
    monkeypatch.setenv("INK_DISABLE_CACHE", "1")
    LLAMADAS["n"] = 0

    _lectura_cache(2)
    _lectura_cache(2)

    assert LLAMADAS["n"] == 2


def test_cache_activa_reutiliza_resultado(monkeypatch):
    monkeypatch.delenv("INK_DISABLE_CACHE", raising=False)
    _lectura_cache.clear()
    LLAMADAS["n"] = 0

    assert _lectura_cache(3) == 6
    assert _lectura_cache(3) == 6

    assert LLAMADAS["n"] == 1
    _lectura_cache.clear()
