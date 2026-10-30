"""Terreno que usa el autómata: el DEM con los hoyos rellenados.

El Copernicus DEM es un modelo de superficie (DSM): incluye árboles y casas, que
dejan hoyos de algunos metros en el fondo de las barrancas. Con los volúmenes
de las tormentas de 2019 (~10⁴ m³) el lodo se queda atrapado en esos hoyos a
pocos km de la fuente aunque no tenga resistencia (v1), y entonces la
resistencia de v2 no tiene nada que controlar. Por eso el modelo corre sobre el
DEM acondicionado igual que en src.inputs.cuenca (rellenar hoyos, depresiones y
resolver zonas planas), y así quien detiene el lodo es la física de v2, no el
ruido del DSM. Ver results/modelo/registro_iteraciones.md, v2.1.

Uso:
    from src.modelo.terreno import cargar_dem
    dem = cargar_dem()             # relleno (se guarda la primera vez)
    dem = cargar_dem(relleno=False)  # DEM original
"""

import numpy as np
import rasterio

from src.config import PROCESSED, RAW

DEM = RAW / "dem" / "dem_fuego_30m.tif"
DEM_RELLENO = PROCESSED / "dem_relleno.tif"


def rellenar(ruta_dem=DEM, salida=DEM_RELLENO):
    """Rellena hoyos y depresiones con pysheds y guarda el resultado en la cuadrícula del DEM."""
    if not hasattr(np, "in1d"):  # pysheds 0.5 con NumPy 2.4
        np.in1d = np.isin
    from pysheds.grid import Grid

    grid = Grid.from_raster(str(ruta_dem))
    dem = grid.read_raster(str(ruta_dem))
    relleno = np.asarray(grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem))),
                         dtype="float32")
    with rasterio.open(ruta_dem) as src:
        perfil = src.profile
    salida.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(salida, "w", **perfil) as dst:
        dst.write(relleno, 1)
    return salida


def cargar_dem(relleno=True):
    """DEM en float64 listo para `simular`."""
    ruta = DEM
    if relleno:
        if not DEM_RELLENO.exists():
            rellenar()
        ruta = DEM_RELLENO
    with rasterio.open(ruta) as src:
        return src.read(1).astype("float64")
