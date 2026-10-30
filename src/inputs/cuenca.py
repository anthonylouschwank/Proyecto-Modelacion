"""Cuenca, cauce y fuente de la barranca Las Lajas a partir del DEM.

Pasos (con pysheds): rellenar hoyos y depresiones, resolver zonas planas,
dirección de flujo D8 y acumulación. Luego:

1. Fuente: un punto escogido a mano sobre Las Lajas (FUENTE_MANUAL_UTM) que se
   ajusta (*snap*) a la celda de mayor acumulación en un radio pequeño.
2. Cuenca: todas las celdas que drenan hacia la fuente.
3. Cauce: el camino D8 desde la fuente hasta el borde de la zona, con la
   distancia a lo largo del cauce.
4. Confluencia con el Guacalate: el primer punto del cauce donde el área
   drenada salta (entra un río mucho más grande). Hasta ahí es Las Lajas; más
   abajo el cauce es el Guacalate, cuyos cambios no se deben solo a los lahares
   de Las Lajas. El área drenada justo antes de la confluencia (`area_lajas_m2`)
   es la que escurre hacia la barranca y alimenta el volumen del lahar.

¿Por qué esa fuente? Es la celda más alta del cauce principal de Las Lajas en
el DEM con al menos ~0.3 km² de área drenada (1855 m): ahí el cauce ya está
bien definido al salir del cono y sigue los depósitos grises de la imagen
Sentinel-2 del 2019-03-26. Más arriba el cauce se divide en surcos paralelos
de pocas celdas y un error de una celda manda el lodo a la barranca del oeste
(ver results/modelo/registro_iteraciones.md, v1.0).

Uso:
    python -m src.inputs.cuenca
    python -m src.inputs.cuenca --fuente 731100,1599450   # otra fuente (x, y UTM)

Salidas (en la cuadrícula del DEM):
    data/processed/lajas_fuente.json
    data/processed/lajas_cuenca.tif
    data/processed/lajas_cauce.tif
    data/processed/lajas_cauce_distancia.tif
    results/montecarlo/cuenca_lajas.png
"""

import argparse
import json

import numpy as np
import rasterio

from src.config import PROCESSED, RAIZ, RAW, RES_DEM

# pysheds 0.5 todavía usa np.in1d, que NumPy 2.4 eliminó. Es la misma función que np.isin.
if not hasattr(np, "in1d"):
    np.in1d = np.isin
from pysheds.grid import Grid  # noqa: E402

DEM = RAW / "dem" / "dem_fuego_30m.tif"
RESULTADOS = RAIZ / "results" / "montecarlo"

# Punto escogido a mano sobre Las Lajas (UTM 15N): celda (285, 810), a 1855 m.
FUENTE_MANUAL_UTM = (731_115, 1_599_435)
RADIO_SNAP = 2  # celdas; más grande y el snap puede saltar a la barranca vecina
SALTO_CONFLUENCIA = 5  # el área drenada se multiplica al menos por esto al entrar un río

# Códigos D8 de pysheds (N, NE, E, SE, S, SO, O, NO) → desplazamiento (fila, col).
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
_PASO = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1),
         4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}


def flujo(ruta_dem=DEM):
    """Dirección de flujo D8 y acumulación (en número de celdas) sobre el DEM acondicionado."""
    grid = Grid.from_raster(str(ruta_dem))
    dem = grid.read_raster(str(ruta_dem))
    acondicionado = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
    fdir = grid.flowdir(acondicionado, dirmap=DIRMAP)
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    return grid, fdir, np.asarray(acc, dtype="float64")


def snap(acc, fila, col, radio=RADIO_SNAP):
    """Celda de mayor acumulación en una ventana de (2·radio + 1)² alrededor de (fila, col)."""
    f0, c0 = max(fila - radio, 0), max(col - radio, 0)
    ventana = acc[f0:fila + radio + 1, c0:col + radio + 1]
    i, j = np.unravel_index(np.argmax(ventana), ventana.shape)
    return int(f0 + i), int(c0 + j)


def trazar_cauce(fdir, fuente):
    """Camino D8 desde la fuente hasta salir de la zona (o hasta un sumidero).

    Devuelve (máscara uint8, distancia float32 en m a lo largo del cauce, NaN fuera).
    """
    fdir = np.asarray(fdir)
    nf, nc = fdir.shape
    cauce = np.zeros((nf, nc), dtype="uint8")
    distancia = np.full((nf, nc), np.nan, dtype="float32")
    (i, j), d = fuente, 0.0
    while 0 <= i < nf and 0 <= j < nc and not cauce[i, j]:
        cauce[i, j] = 1
        distancia[i, j] = d
        paso = _PASO.get(int(fdir[i, j]))
        if paso is None:  # sumidero o celda sin dirección
            break
        i, j = i + paso[0], j + paso[1]
        d += RES_DEM * (np.sqrt(2.0) if paso[0] and paso[1] else 1.0)
    return cauce, distancia


def confluencia(acc, distancia):
    """Primer punto del cauce donde el área drenada salta SALTO_CONFLUENCIA veces.

    Devuelve (fila, col, distancia en m, área drenada justo antes en m²).
    """
    filas, cols = np.nonzero(np.isfinite(distancia))
    orden = np.argsort(distancia[filas, cols])
    filas, cols = filas[orden], cols[orden]
    a = acc[filas, cols]
    for k in range(1, len(a)):
        if a[k] >= SALTO_CONFLUENCIA * a[k - 1]:
            return (int(filas[k]), int(cols[k]), float(distancia[filas[k], cols[k]]),
                    float(a[k - 1]) * RES_DEM**2)
    raise ValueError("No se encontró la confluencia en el cauce")


def cuenca_lajas(fuente_utm=FUENTE_MANUAL_UTM):
    """Calcula fuente, cuenca, cauce y distancia. Devuelve un diccionario con todo."""
    with rasterio.open(DEM) as src:
        z = src.read(1)
        perfil = src.profile
        fila0, col0 = src.index(*fuente_utm)

    grid, fdir, acc = flujo()
    fila, col = snap(acc, fila0, col0)
    x, y = rasterio.transform.xy(perfil["transform"], fila, col)  # centro de la celda

    cuenca = np.asarray(grid.catchment(x=col, y=fila, fdir=fdir, dirmap=DIRMAP,
                                       xytype="index"), dtype="uint8")
    cauce, distancia = trazar_cauce(fdir, (fila, col))

    area = float(cuenca.sum()) * RES_DEM**2
    cf, cc, d_conf, area_lajas = confluencia(acc, distancia)
    fuente = {
        "fila": fila, "col": col, "x": float(x), "y": float(y),
        "z": round(float(z[fila, col]), 1), "area_cuenca_m2": area,
        "confluencia": [cf, cc], "km_confluencia": round(d_conf / 1000, 2),
        "area_lajas_m2": area_lajas,
    }
    return dict(fuente=fuente, cuenca=cuenca, cauce=cauce, distancia=distancia,
                acc=acc, z=z, perfil=perfil, manual=(fila0, col0))


def guardar(r):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "lajas_fuente.json").write_text(json.dumps(r["fuente"], indent=2))

    base = dict(r["perfil"], count=1, compress="deflate")
    for nombre, datos, dtype, nodata in [
        ("lajas_cuenca.tif", r["cuenca"], "uint8", None),
        ("lajas_cauce.tif", r["cauce"], "uint8", None),
        ("lajas_cauce_distancia.tif", r["distancia"], "float32", np.nan),
    ]:
        with rasterio.open(PROCESSED / nombre, "w", **dict(base, dtype=dtype, nodata=nodata)) as dst:
            dst.write(datos.astype(dtype), 1)


def figura(r, ruta):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, ListedColormap

    z, cuenca, cauce, f = r["z"], r["cuenca"], r["cauce"], r["fuente"]
    sombra = LightSource(315, 45).hillshade(z, vert_exag=2, dx=RES_DEM, dy=RES_DEM)
    b = rasterio.transform.array_bounds(*z.shape, r["perfil"]["transform"])
    extent = (b[0], b[2], b[1], b[3])
    azul = ListedColormap(["none", "deepskyblue"])
    rojo = ListedColormap(["none", "red"])

    fig, ejes = plt.subplots(1, 2, figsize=(16, 8))
    # Izquierda: toda la zona sobre el sombreado. Derecha: acercamiento a la fuente.
    filas, cols = np.nonzero(cuenca)
    m = 25
    r0, r1 = filas.min() - m, filas.max() + 3 * m
    c0, c1 = cols.min() - m, cols.max() + 3 * m
    xmin, ymax = extent[0], extent[3]
    zoom = (xmin + c0 * RES_DEM, xmin + c1 * RES_DEM, ymax - r1 * RES_DEM, ymax - r0 * RES_DEM)

    rgb = RAW / "sentinel2" / "s2_20190326_rgb.png"
    for ax, acerc in zip(ejes, (False, True)):
        if acerc and rgb.exists():
            ax.imshow(plt.imread(rgb), extent=extent)
        else:
            ax.imshow(sombra, cmap="gray", extent=extent)
        ax.imshow(np.ma.masked_equal(cuenca, 0), cmap=azul, vmin=0, vmax=1, alpha=0.5, extent=extent,
                  interpolation="nearest")
        ax.imshow(np.ma.masked_equal(cauce, 0), cmap=rojo, vmin=0, vmax=1, extent=extent,
                  interpolation="nearest")
        ax.plot(f["x"], f["y"], "y*", ms=16, mec="k", label=f"Fuente ({f['z']:.0f} m)")
        ax.set_xlabel("Este (m)")
        ax.set_ylabel("Norte (m)")
        if acerc:
            ax.set_xlim(zoom[0], zoom[1])
            ax.set_ylim(zoom[2], zoom[3])
            ax.set_title("Acercamiento sobre Sentinel-2 (2019-03-26)")
        else:
            ax.plot([], [], "s", color="deepskyblue", label="Cuenca")
            ax.plot([], [], "-", color="red", label="Cauce")
            ax.set_title("Las Lajas: cuenca, cauce y fuente")
            ax.legend(loc="lower left")
    fig.suptitle(f"Área de la cuenca: {f['area_cuenca_m2'] / 1e6:.2f} km²  ·  "
                 f"cauce: {np.nanmax(r['distancia']) / 1000:.1f} km hasta el borde")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", help="x,y en UTM 15N (por defecto, FUENTE_MANUAL_UTM)")
    args = parser.parse_args()
    fuente_utm = (tuple(float(v) for v in args.fuente.split(","))
                  if args.fuente else FUENTE_MANUAL_UTM)

    r = cuenca_lajas(fuente_utm)
    guardar(r)
    f = r["fuente"]
    print(f"Fuente: celda ({f['fila']}, {f['col']}) a {f['z']:.0f} m "
          f"(punto manual en {r['manual']}, snap de {RADIO_SNAP} celdas)")
    print(f"  UTM: x {f['x']:.0f}, y {f['y']:.0f}")
    print(f"  área de la cuenca: {f['area_cuenca_m2'] / 1e6:.3f} km²")
    print(f"  confluencia con el Guacalate en el km {f['km_confluencia']}, celda "
          f"{tuple(f['confluencia'])}; área de Las Lajas hasta ahí: {f['area_lajas_m2'] / 1e6:.2f} km²")
    print(f"  cauce: {int(r['cauce'].sum())} celdas, "
          f"{np.nanmax(r['distancia']) / 1000:.1f} km hasta el borde de la zona")
    print(f"Guardado en {PROCESSED}")
    ruta = RESULTADOS / "cuenca_lajas.png"
    figura(r, ruta)
    print(f"Figura: {ruta}")


if __name__ == "__main__":
    main()
