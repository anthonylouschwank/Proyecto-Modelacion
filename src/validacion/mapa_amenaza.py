"""Clasifica el mapa de amenaza de lahares del INSIVUMEH (escenario B) por color.

El GeoTIFF del INSIVUMEH es la imagen del mapa: zonas semitransparentes roja
(alta), naranja (media) y amarilla (baja) sobre una imagen satelital. Cada
píxel se clasifica por tono, saturación y brillo (HSV); los rangos se
escogieron muestreando las zonas del mapa y el fondo (vegetación y campos
tienen saturación o brillo más bajos).

Luego:
1. Apertura morfológica por clase para quitar texto, carreteras y el rayado
   del depósito piroclástico.
2. Paso a la cuadrícula del DEM (30 m): cada celda toma la clase más alta que
   cubra al menos la mitad de la celda.

Uso:
    python -m src.validacion.mapa_amenaza

Salidas:
    data/processed/amenaza_insivumeh_B.tif  (uint8: 0 nada, 1 baja, 2 media, 3 alta)
    results/validacion/amenaza_insivumeh_B.png
"""

import numpy as np
import rasterio
from matplotlib.colors import rgb_to_hsv
from rasterio.warp import Resampling, reproject
from scipy import ndimage

from src.config import PROCESSED, RAIZ, RAW

MAPA = RAW / "insivumeh" / "fuego_lahares_escenario_B.tif"
DEM = RAW / "dem" / "dem_fuego_30m.tif"
SALIDA = PROCESSED / "amenaza_insivumeh_B.tif"
FIGURA = RAIZ / "results" / "validacion" / "amenaza_insivumeh_B.png"

# (tono en grados, saturación mínima, brillo mínimo) por clase.
ALTA = ((345, 15), 0.45, 0.35)    # rojo (el rango cruza 0°)
MEDIA = ((25, 50), 0.55, 0.45)    # naranja
BAJA = ((45, 75), 0.30, 0.65)     # amarillo
APERTURA = 3  # píxeles de ~5.5 m


def clasificar_pixeles(rgb):
    """RGB (3, alto, ancho) uint8 → clases 0–3 a la resolución del mapa."""
    hsv = rgb_to_hsv(np.moveaxis(rgb, 0, -1) / 255.0)
    tono, sat, brillo = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]

    def es(rango, s_min, v_min, cruza_cero=False):
        a, b = rango
        en_tono = (tono >= a) | (tono < b) if cruza_cero else (tono >= a) & (tono < b)
        return en_tono & (sat >= s_min) & (brillo >= v_min)

    clases = np.zeros(tono.shape, dtype="uint8")
    clases[es(*BAJA)] = 1
    clases[es(*MEDIA)] = 2
    clases[es(*ALTA, cruza_cero=True)] = 3

    estructura = np.ones((APERTURA, APERTURA), dtype=bool)
    limpio = np.zeros_like(clases)
    for k in (1, 2, 3):
        limpio[ndimage.binary_opening(clases == k, structure=estructura)] = k
    return limpio


def a_cuadricula_dem(clases, transform, crs):
    """Clase más alta que cubre al menos la mitad de cada celda de 30 m."""
    with rasterio.open(DEM) as ref:
        perfil = ref.profile
    salida = np.zeros((perfil["height"], perfil["width"]), dtype="uint8")
    for k in (1, 2, 3):
        fraccion = np.zeros(salida.shape, dtype="float32")
        reproject(source=(clases >= k).astype("float32"), destination=fraccion,
                  src_transform=transform, src_crs=crs,
                  dst_transform=perfil["transform"], dst_crs=perfil["crs"],
                  resampling=Resampling.average)
        salida[fraccion >= 0.5] = k
    return salida, perfil


def figura(amenaza, ruta):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    colores = ListedColormap(["#ffffff", "#f2e35c", "#f29c2b", "#d1312b"])
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(amenaza, cmap=colores, vmin=0, vmax=3, interpolation="nearest")
    ax.legend(handles=[Patch(color=c, label=n) for c, n in
                       zip(colores.colors[1:], ("baja", "media", "alta"))], loc="lower left")
    ax.set_title("Amenaza de lahares INSIVUMEH (escenario B), cuadrícula de 30 m")
    ax.axis("off")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main():
    with rasterio.open(MAPA) as src:
        rgb = src.read([1, 2, 3])
        transform, crs = src.transform, src.crs
    clases = clasificar_pixeles(rgb)
    amenaza, perfil = a_cuadricula_dem(clases, transform, crs)

    perfil.update(dtype="uint8", nodata=None, count=1, compress="deflate")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(SALIDA, "w", **perfil) as dst:
        dst.write(amenaza, 1)
    for k, nombre in ((1, "baja"), (2, "media"), (3, "alta")):
        print(f"  {nombre}: {(amenaza == k).sum() * 900 / 1e6:.1f} km²")
    figura(amenaza, FIGURA)
    print(f"Guardado {SALIDA}\nFigura {FIGURA}")


if __name__ == "__main__":
    main()
