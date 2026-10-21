"""Descarga el modelo de elevación (Copernicus DEM GLO-30) de la zona de estudio.

Los tiles se leen directo del bucket público de AWS (sin cuenta), se unen,
se recortan a la AOI y se reproyectan a UTM 15N con celdas de 30 m.

Uso:
    python -m src.inputs.dem            # descarga y guarda el GeoTIFF
    python -m src.inputs.dem --preview  # además guarda una vista previa PNG

Salida: data/raw/dem/dem_fuego_30m.tif
"""

import argparse
import math

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds

from src.config import AOI, CRATER_UTM, CRS, RAW, RES_DEM

URL_TILE = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM/"
    "Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM.tif"
)
SALIDA = RAW / "dem" / "dem_fuego_30m.tif"


def urls_tiles(lon_min, lat_min, lon_max, lat_max):
    """Tiles de 1°×1° que cubren el rectángulo. Cada tile se nombra por su esquina SO."""
    urls = []
    for lat in range(math.floor(lat_min), math.floor(lat_max) + 1):
        for lon in range(math.floor(lon_min), math.floor(lon_max) + 1):
            ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
            ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
            urls.append(URL_TILE.format(lat=ns, lon=ew))
    return urls


def descargar_dem():
    xmin, ymin, xmax, ymax = AOI
    # Margen de ~0.01° para que la reproyección no deje bordes vacíos.
    lon_min, lat_min, lon_max, lat_max = transform_bounds(CRS, "EPSG:4326", *AOI)
    bounds_ll = (lon_min - 0.01, lat_min - 0.01, lon_max + 0.01, lat_max + 0.01)

    urls = urls_tiles(*bounds_ll)
    print(f"Leyendo {len(urls)} tile(s) de Copernicus DEM:")
    for u in urls:
        print("  ", u.rsplit("/", 1)[-1])

    fuentes = [rasterio.open(u) for u in urls]
    try:
        mosaico, transf_ll = merge(fuentes, bounds=bounds_ll)
        crs_ll = fuentes[0].crs
    finally:
        for f in fuentes:
            f.close()

    ancho = round((xmax - xmin) / RES_DEM)
    alto = round((ymax - ymin) / RES_DEM)
    transf = from_origin(xmin, ymax, RES_DEM, RES_DEM)
    dem = np.full((alto, ancho), np.nan, dtype="float32")
    reproject(
        source=mosaico[0],
        destination=dem,
        src_transform=transf_ll,
        src_crs=crs_ll,
        dst_transform=transf,
        dst_crs=CRS,
        resampling=Resampling.bilinear,
        dst_nodata=np.nan,
    )

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    perfil = dict(
        driver="GTiff", dtype="float32", count=1, width=ancho, height=alto,
        crs=CRS, transform=transf, nodata=np.nan,
        compress="deflate", tiled=True, blockxsize=256, blockysize=256,
    )
    with rasterio.open(SALIDA, "w", **perfil) as dst:
        dst.write(dem, 1)

    print(f"Guardado {SALIDA} ({alto}×{ancho} celdas de {RES_DEM} m)")
    print(f"Elevación: min {np.nanmin(dem):.0f} m, max {np.nanmax(dem):.0f} m, "
          f"celdas vacías: {np.isnan(dem).sum()}")
    return SALIDA


def vista_previa(ruta=SALIDA):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource

    with rasterio.open(ruta) as src:
        dem = src.read(1)
        b = src.bounds
    sombra = LightSource(azdeg=315, altdeg=45).hillshade(
        np.nan_to_num(dem, nan=np.nanmin(dem)), vert_exag=2, dx=RES_DEM, dy=RES_DEM
    )
    extent = (b.left, b.right, b.bottom, b.top)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(sombra, cmap="gray", extent=extent)
    im = ax.imshow(dem, cmap="terrain", alpha=0.45, extent=extent)
    ax.plot(*CRATER_UTM, "r^", ms=10, label="Cráter Volcán de Fuego")
    fig.colorbar(im, ax=ax, shrink=0.7, label="Elevación (m)")
    ax.set_title("Copernicus DEM GLO-30 – zona de estudio (UTM 15N)")
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    ax.legend(loc="lower left")
    salida_png = ruta.with_suffix(".png")
    fig.savefig(salida_png, dpi=120, bbox_inches="tight")
    print(f"Vista previa: {salida_png}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", action="store_true", help="guardar vista previa PNG")
    args = parser.parse_args()
    ruta = descargar_dem()
    if args.preview:
        vista_previa(ruta)
