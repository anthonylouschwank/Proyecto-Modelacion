"""Corre el autómata en Las Lajas con un volumen fijo y guarda una figura.

Uso:
    python -m src.modelo.demo --version v1 --volumen 5e5
    python -m src.modelo.demo --version v1 --volumen 1e6 --pasos-fuente 100
    python -m src.modelo.demo --fuente 285,790 --etiqueta fuente_oeste

La fuente se lee de data/processed/lajas_fuente.json (lo genera P2). Si
todavía no existe, se usa una fuente provisional: la celda (294, 822), a
1731 m, sobre el cauce de Las Lajas unos 380 m abajo de la divisoria con la
barranca del oeste. Ojo: un poco más arriba (ej. 285, 790) el lodo se va por
la otra barranca.

Salida: results/modelo/<version>_lajas_<volumen>[_<etiqueta>].png
"""

import argparse
import json
import time

import numpy as np
import rasterio

from src.config import AOI, PROCESSED, RAIZ, RAW, RES_DEM
from src.modelo.automata import Parametros, simular

FUENTE_PROVISIONAL = (294, 822)
SALIDA_DIR = RAIZ / "results" / "modelo"


def cargar_fuente():
    ruta = PROCESSED / "lajas_fuente.json"
    if ruta.exists():
        f = json.loads(ruta.read_text())
        return (f["fila"], f["col"]), "lajas_fuente.json"
    return FUENTE_PROVISIONAL, "provisional"


def figura(res, dem, fuente, titulo, ruta):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, LogNorm

    filas, cols = np.nonzero(res.h_max > 0.01)
    margen = 40
    r0, r1 = max(filas.min() - margen, 0), min(filas.max() + margen, dem.shape[0])
    c0, c1 = max(cols.min() - margen, 0), min(cols.max() + margen, dem.shape[1])
    xmin, _, _, ymax = AOI
    extent = (xmin + c0 * RES_DEM, xmin + c1 * RES_DEM,
              ymax - r1 * RES_DEM, ymax - r0 * RES_DEM)

    fig, ax = plt.subplots(figsize=(8, 9))
    rgb = RAW / "sentinel2" / "s2_20190326_rgb.png"
    if rgb.exists():
        fondo = plt.imread(rgb)[r0:r1, c0:c1]
        ax.imshow(fondo, extent=extent)
    else:
        sombra = LightSource(315, 45).hillshade(dem[r0:r1, c0:c1], vert_exag=2,
                                                dx=RES_DEM, dy=RES_DEM)
        ax.imshow(sombra, cmap="gray", extent=extent)

    h = np.ma.masked_less_equal(res.h_max[r0:r1, c0:c1], 0.1)
    im = ax.imshow(h, cmap="inferno_r", norm=LogNorm(0.1, max(h.max(), 1)),
                   extent=extent, alpha=0.8)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Espesor máximo de lodo (m)")
    x = xmin + (fuente[1] + 0.5) * RES_DEM
    y = ymax - (fuente[0] + 0.5) * RES_DEM
    ax.plot(x, y, "c*", ms=14, mec="k", label="Fuente")
    ax.set_title(titulo)
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    ax.legend(loc="upper right")
    fig.savefig(ruta, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default="v1")
    parser.add_argument("--volumen", type=float, default=5e5, help="m³")
    parser.add_argument("--relajacion", type=float, default=0.5)
    parser.add_argument("--pasos-fuente", type=int, default=Parametros.pasos_fuente)
    parser.add_argument("--max-pasos", type=int, default=20_000)
    parser.add_argument("--fuente", help="fila,col (por defecto, lajas_fuente.json o la provisional)")
    parser.add_argument("--etiqueta", help="sufijo para el nombre de la figura")
    args = parser.parse_args()

    with rasterio.open(RAW / "dem" / "dem_fuego_30m.tif") as src:
        dem = src.read(1).astype("float64")
    if args.fuente:
        fuente, origen = tuple(int(v) for v in args.fuente.split(",")), "--fuente"
    else:
        fuente, origen = cargar_fuente()
    params = Parametros(relajacion=args.relajacion, pasos_fuente=args.pasos_fuente,
                        max_pasos=args.max_pasos)

    print(f"Fuente {fuente} ({origen}), z = {dem[fuente]:.0f} m; "
          f"volumen {args.volumen:.2e} m³; {args.version}")
    t = time.perf_counter()
    res = simular(dem, fuente, args.volumen, params, version=args.version)
    seg = time.perf_counter() - t

    alc = res.alcanzado
    filas, cols = np.nonzero(alc)
    dist = np.hypot(filas - fuente[0], cols - fuente[1]).max() * RES_DEM
    z_min = dem[alc].min()
    print(f"  {res.pasos} pasos en {seg:.1f} s (convergió: {res.convergio})")
    print(f"  área alcanzada: {alc.sum() * RES_DEM**2 / 1e6:.2f} km²")
    print(f"  alcance en línea recta: {dist / 1000:.1f} km (hasta {z_min:.0f} m de altura)")
    print(f"  salió de la zona: {res.volumen_perdido / args.volumen:.1%} del volumen")
    print(f"  espesor máximo: {res.h_max.max():.1f} m")

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    sufijo = f"_{args.etiqueta}" if args.etiqueta else ""
    ruta = SALIDA_DIR / f"{args.version}_lajas_{args.volumen:.0e}{sufijo}.png"
    titulo = (f"{args.version} – Las Lajas, V = {args.volumen:.0e} m³\n"
              f"{res.pasos} pasos, alcance {dist / 1000:.1f} km, "
              f"{res.volumen_perdido / args.volumen:.0%} salió de la zona")
    figura(res, dem, fuente, titulo, ruta)
    print(f"  figura: {ruta}")


if __name__ == "__main__":
    main()
