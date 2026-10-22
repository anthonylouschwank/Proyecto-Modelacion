"""Descarga el recorte de la AOI de una fecha de Sentinel-2 L2A.

Guarda, a 10 m en UTM 15N:
  - s2_<fecha>_refl.tif : banda 1 = rojo (B04), banda 2 = NIR (B08), en reflectancia
  - s2_<fecha>_scl.tif  : máscara de clasificación (nubes, sombras, agua…)
  - s2_<fecha>_rgb.png  : vista previa en color verdadero, para revisar a ojo

Uso:
    python -m src.sentinel.descargar --fecha 2019-12-26
"""

import argparse
from datetime import date

import numpy as np
import rasterio
from rasterio.merge import merge

from src.config import AOI, CRS, RAW, RES_S2
from src.sentinel.stac import buscar_por_fecha, escala_offset, mosaico

SALIDA_DIR = RAW / "sentinel2"


def guardar(ruta, bandas, transf, dtype, nodata, descripciones):
    alto, ancho = bandas[0].shape
    perfil = dict(
        driver="GTiff", dtype=dtype, count=len(bandas), width=ancho, height=alto,
        crs=CRS, transform=transf, nodata=nodata,
        compress="deflate", tiled=True, blockxsize=512, blockysize=512,
    )
    with rasterio.open(ruta, "w", **perfil) as dst:
        for i, (banda, desc) in enumerate(zip(bandas, descripciones), start=1):
            dst.write(banda.astype(dtype), i)
            dst.set_band_description(i, desc)


def reflectancia(items, asset):
    dn, transf = mosaico(items, asset, RES_S2)
    escala, offset = escala_offset(items[0], asset)
    refl = np.where(dn == 0, np.nan, dn * escala + offset).astype("float32")
    return refl, transf


def vista_previa(items, ruta):
    import matplotlib.pyplot as plt

    # "visual" es el color verdadero (TCI) ya en 0–255; a 30 m basta para mirar.
    fuentes = [rasterio.open(it.assets["visual"].href) for it in items]
    try:
        rgb, _ = merge(fuentes, bounds=AOI, res=30, nodata=0)
    finally:
        for f in fuentes:
            f.close()
    plt.imsave(ruta, np.moveaxis(rgb, 0, -1))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fecha", required=True, type=date.fromisoformat, help="AAAA-MM-DD")
    args = parser.parse_args()

    items = buscar_por_fecha(args.fecha, args.fecha, max_nubes_tile=100).get(args.fecha)
    if not items:
        raise SystemExit(f"No hay escenas de Sentinel-2 sobre la AOI el {args.fecha}")
    print(f"{args.fecha}: {len(items)} tile(s): {', '.join(it.id for it in items)}")

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    base = SALIDA_DIR / f"s2_{args.fecha:%Y%m%d}"

    print("  rojo (B04) y NIR (B08) a 10 m…")
    rojo, transf = reflectancia(items, "red")
    nir, _ = reflectancia(items, "nir")
    guardar(f"{base}_refl.tif", [rojo, nir], transf, "float32", np.nan, ["B04_rojo", "B08_nir"])

    print("  máscara SCL (20 m → 10 m)…")
    scl, _ = mosaico(items, "scl", RES_S2)
    guardar(f"{base}_scl.tif", [scl], transf, "uint8", 0, ["SCL"])

    print("  vista previa RGB…")
    vista_previa(items, f"{base}_rgb.png")

    print(f"Guardado {base}_refl.tif, {base}_scl.tif, {base}_rgb.png")


if __name__ == "__main__":
    main()
