"""
Tests for Chilean RUT validation and normalization.
"""
import pytest
from core.utils import normalizar_rut, validar_rut, formatear_rut, limpiar_rut
from core.exceptions import InvalidRUTError


class TestRUT:
    def test_limpiar_rut(self):
        assert limpiar_rut("12.345.678-9") == "123456789"
        assert limpiar_rut("12345678-9") == "123456789"
        assert limpiar_rut("12345678k") == "12345678K"
    
    def test_normalizar_rut(self):
        assert normalizar_rut("12.345.678-9") == "123456789"
        assert normalizar_rut("12345678-k") == "12345678K"
        assert normalizar_rut("11.111.111-1") == "111111111"
    
    def test_normalizar_rut_invalido(self):
        with pytest.raises(InvalidRUTError):
            normalizar_rut("")
        with pytest.raises(InvalidRUTError):
            normalizar_rut("123")
    
    def test_validar_rut_valido(self):
        # RUTs válidos de ejemplo
        assert validar_rut("11.111.111-1") == True
        assert validar_rut("22.222.222-2") == True
    
    def test_validar_rut_invalido(self):
        assert validar_rut("11.111.111-2") == False
        assert validar_rut("123") == False
        assert validar_rut("") == False
    
    def test_formatear_rut(self):
        assert formatear_rut("123456789") == "12.345.678-9"
        assert formatear_rut("111111111") == "11.111.111-1"
    
    def test_rut_sin_puntos_guiones(self):
        # Debe normalizar correctamente
        rut_norm = normalizar_rut("111111111")
        assert rut_norm == "111111111"
        assert validar_rut(rut_norm) == True
