"""Genera las imágenes optimizadas de la interfaz a partir de `imagenes/`.

Uso (desde la raíz del proyecto):
    python scripts/generar_imagenes.py

Originales (no se modifican):
    imagenes/logo.PNG    logo en negro sobre fondo blanco
    imagenes/fondo.jpeg  fotografía del escenario del local

Resultado en `static/` (Streamlit la publica con enableStaticServing):
    logo_blanco.png  logo blanco con fondo transparente (fondos oscuros)
    logo_negro.png   logo negro con fondo transparente (fondos claros)
    icono.png        ícono cuadrado para la pestaña del navegador
    fondo.jpg        fotografía comprimida para el login y el inicio
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "imagenes"
DESTINO = RAIZ / "static"  # Streamlit la publica en app/static/

ANCHO_LOGO = 520
LADO_ICONO = 128
ANCHO_FONDO = 1280


def _mascara_tinta(logo: Image.Image) -> Image.Image:
    """Canal alfa a partir de la tinta: negro = opaco, blanco = transparente."""
    gris = ImageOps.grayscale(logo)
    # Se refuerza el contraste para que el blanco de fondo quede limpio.
    return ImageOps.invert(gris).point(lambda v: 0 if v < 40 else min(255, int(v * 1.15)))


def _logo_color(mascara: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    capa = Image.new("RGBA", mascara.size, color + (0,))
    capa.putalpha(mascara)
    return capa


def _recortar(imagen: Image.Image) -> Image.Image:
    caja = imagen.getbbox()
    return imagen.crop(caja) if caja else imagen


def _escalar(imagen: Image.Image, ancho: int) -> Image.Image:
    if imagen.width <= ancho:
        return imagen
    alto = round(imagen.height * ancho / imagen.width)
    return imagen.resize((ancho, alto), Image.LANCZOS)


def main() -> None:
    DESTINO.mkdir(exist_ok=True)

    logo = Image.open(ORIGEN / "logo.PNG").convert("RGB")
    mascara = _mascara_tinta(logo)

    blanco = _escalar(_recortar(_logo_color(mascara, (255, 255, 255))), ANCHO_LOGO)
    negro = _escalar(_recortar(_logo_color(mascara, (17, 17, 19))), ANCHO_LOGO)
    blanco.save(DESTINO / "logo_blanco.png", optimize=True)
    negro.save(DESTINO / "logo_negro.png", optimize=True)

    # Ícono: logo vino sobre fondo claro, centrado en un cuadrado.
    vino = _recortar(_logo_color(mascara, (128, 0, 32)))
    vino.thumbnail((LADO_ICONO - 8, LADO_ICONO - 8), Image.LANCZOS)
    icono = Image.new("RGBA", (LADO_ICONO, LADO_ICONO), (255, 255, 255, 255))
    icono.alpha_composite(
        vino, ((LADO_ICONO - vino.width) // 2, (LADO_ICONO - vino.height) // 2)
    )
    icono.save(DESTINO / "icono.png", optimize=True)

    fondo = Image.open(ORIGEN / "fondo.jpeg").convert("RGB")
    _escalar(fondo, ANCHO_FONDO).save(
        DESTINO / "fondo.jpg", quality=78, optimize=True, progressive=True
    )

    for archivo in ("logo_blanco.png", "logo_negro.png", "icono.png", "fondo.jpg"):
        ruta = DESTINO / archivo
        print(f"{archivo}: {ruta.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
