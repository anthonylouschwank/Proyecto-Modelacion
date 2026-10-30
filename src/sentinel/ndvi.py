"""Mapa de lo observado: dónde pasó el lodo en Las Lajas en cada periodo de 2019.

Compara el NDVI de Sentinel-2 antes y después de cada periodo y clasifica cada
píxel de 10 m dentro del corredor de la barranca:
    2 = cambio seguro: había vegetación y ya no (NDVI_antes >= 0.4 y ΔNDVI >= 0.25)
    1 = posible: desnudo al final (NDVI_después < 0.2), pero ya lo estaba al inicio
    0 = vegetación al final
    255 = sin dato: nube, sombra o sin imagen en alguna fecha, o fuera del corredor

Luego quita manchas aisladas y las que no tocan el cauce (parcelas agrícolas
cosechadas: el lodo se desborda desde el cauce, una parcela suelta no), y pasa
a la cuadrícula del DEM (3 × 3 píxeles de 10 m = 1 celda de 30 m) por mayoría.

Uso:
    python -m src.sentinel.ndvi                 # p1 y p2
    python -m src.sentinel.ndvi --periodo p1

Requiere: las 3 fechas de src.sentinel.descargar y python -m src.inputs.cuenca.

Salidas:
    data/processed/observado_lajas_2019_<periodo>.tif
    results/sentinel/ndvi_<periodo>.png, observado_<periodo>.png, histogramas.png
"""

import argparse
import json

import numpy as np
import rasterio
from scipy import ndimage

from src.config import PROCESSED, RAIZ, RAW, RES_DEM, RES_S2

S2_DIR = RAW / "sentinel2"
DEM = RAW / "dem" / "dem_fuego_30m.tif"
SALIDA_DIR = RAIZ / "results" / "sentinel"

PERIODOS = {"p1": ("20190326", "20190704"), "p2": ("20190704", "20191211")}

# Umbrales congelados antes de la calibración (ver results/sentinel/umbrales.md).
NDVI_VEGETACION = 0.4   # antes: había vegetación
DELTA_NDVI = 0.25       # pérdida mínima de NDVI para contar como cambio seguro
NDVI_DESNUDO = 0.2      # después: suelo desnudo
CORREDOR_M = 500        # distancia máxima al cauce de Las Lajas
MANCHA_MIN = 5          # píxeles de 10 m; manchas más chicas se consideran ruido
CONEXION_M = 100        # una mancha cuenta solo si llega a esta distancia del cauce

SIN_DATO = 255
# SCL: sin dato, píxel oscuro/sombra topográfica, sombra de nube, nubes y cirros.
SCL_INVALIDO = (0, 2, 3, 8, 9, 10)
FACTOR = RES_DEM // RES_S2  # 3


def leer_fecha(fecha):
    """NDVI y máscara de píxeles válidos de una fecha (10 m)."""
    with rasterio.open(S2_DIR / f"s2_{fecha}_refl.tif") as src:
        rojo, nir = src.read(1), src.read(2)
    with rasterio.open(S2_DIR / f"s2_{fecha}_scl.tif") as src:
        scl = src.read(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir - rojo) / (nir + rojo)
    valido = np.isfinite(ndvi) & ~np.isin(scl, SCL_INVALIDO)
    return ndvi, valido


def corredor():
    """Celdas de 30 m a <= CORREDOR_M del cauce, por debajo de la fuente y antes
    de la confluencia con el Guacalate; y celdas a <= CONEXION_M del cauce (para
    el filtro de conexión).

    Más abajo de la confluencia el cauce es el Guacalate, que cambia por sus
    propias crecidas y por la caña de azúcar: no sirve para validar Las Lajas.
    """
    with rasterio.open(PROCESSED / "lajas_cauce_distancia.tif") as src:
        dist_cauce = src.read(1)
    with rasterio.open(DEM) as src:
        dem = src.read(1)
    fuente = json.loads((PROCESSED / "lajas_fuente.json").read_text())
    cauce = np.isfinite(dist_cauce)
    distancia, (fi, ci) = ndimage.distance_transform_edt(~cauce, return_indices=True)
    distancia *= RES_DEM
    # Distancia por el cauce del punto del cauce más cercano a cada celda.
    km_cauce = dist_cauce[fi, ci] / 1000
    en_lajas = km_cauce <= fuente["km_confluencia"]
    return ((distancia <= CORREDOR_M) & (dem < fuente["z"]) & en_lajas,
            distancia <= CONEXION_M)


def clasificar(ndvi_a, ndvi_d, valido, en_corredor):
    """Clases 0/1/2/255 a 10 m, sin limpiar."""
    seguro = (ndvi_a >= NDVI_VEGETACION) & (ndvi_a - ndvi_d >= DELTA_NDVI)
    posible = (ndvi_d < NDVI_DESNUDO) & ~seguro
    clases = np.where(seguro, 2, np.where(posible, 1, 0)).astype("uint8")
    clases[~(valido & en_corredor)] = SIN_DATO
    return clases


def quitar_manchas(clases, ndvi_d, junto_al_cauce):
    """Manchas de clase 2 o de clase 1–2 con menos de MANCHA_MIN píxeles bajan de clase,
    y las que no tocan `junto_al_cauce` pasan a 0. Las de clase 2 se revisan solas:
    una parcela cosechada junto a la barranca no cuenta solo por tocar la franja desnuda."""
    ocho = np.ones((3, 3), dtype=bool)
    etiquetas, _ = ndimage.label(clases == 2, structure=ocho)
    tam = np.bincount(etiquetas.ravel())
    chicas = (tam[etiquetas] < MANCHA_MIN) & (etiquetas > 0)
    clases[chicas] = np.where(ndvi_d[chicas] < NDVI_DESNUDO, 1, 0)

    etiquetas, _ = ndimage.label((clases == 1) | (clases == 2), structure=ocho)
    tam = np.bincount(etiquetas.ravel())
    clases[(tam[etiquetas] < MANCHA_MIN) & (etiquetas > 0)] = 0

    for mascara in (clases == 2, (clases == 1) | (clases == 2)):
        etiquetas, _ = ndimage.label(mascara, structure=ocho)
        conectadas = np.unique(etiquetas[junto_al_cauce & (etiquetas > 0)])
        clases[(etiquetas > 0) & ~np.isin(etiquetas, conectadas)] = 0
    return clases


def a_30m(clases):
    """3 × 3 píxeles → 1 celda: 255 si más de la mitad no tiene dato; si no, la clase
    mayoritaria entre los válidos (en empate gana la clase más alta)."""
    n, m = clases.shape[0] // FACTOR, clases.shape[1] // FACTOR
    bloques = clases.reshape(n, FACTOR, m, FACTOR).swapaxes(1, 2).reshape(n, m, -1)
    cuentas = np.stack([(bloques == c).sum(-1) for c in (0, 1, 2)], axis=-1)
    # argmax sobre las clases al revés para que el empate favorezca a la más alta.
    salida = (2 - np.argmax(cuentas[..., ::-1], axis=-1)).astype("uint8")
    salida[(bloques == SIN_DATO).sum(-1) > FACTOR * FACTOR // 2] = SIN_DATO
    return salida


def guardar(obs, ruta):
    with rasterio.open(DEM) as ref:
        perfil = ref.profile
    perfil.update(dtype="uint8", nodata=SIN_DATO, count=1, compress="deflate")
    with rasterio.open(ruta, "w", **perfil) as dst:
        dst.write(obs, 1)


def recorte(mascara, margen=20):
    filas, cols = np.nonzero(mascara)
    return (slice(max(filas.min() - margen, 0), filas.max() + margen),
            slice(max(cols.min() - margen, 0), cols.max() + margen))


def figura_ndvi(ndvi_a, ndvi_d, en_corredor, periodo, fechas, ruta):
    import matplotlib.pyplot as plt

    f, c = recorte(en_corredor)
    f10, c10 = slice(f.start * FACTOR, f.stop * FACTOR), slice(c.start * FACTOR, c.stop * FACTOR)
    paneles = [(ndvi_a[f10, c10], f"NDVI {fechas[0]}", "RdYlGn", (-0.2, 0.9)),
               (ndvi_d[f10, c10], f"NDVI {fechas[1]}", "RdYlGn", (-0.2, 0.9)),
               (ndvi_a[f10, c10] - ndvi_d[f10, c10], "ΔNDVI (antes − después)", "PuOr_r", (-0.6, 0.6))]
    fig, ejes = plt.subplots(1, 3, figsize=(15, 7))
    for ax, (img, titulo, cmap, (vmin, vmax)) in zip(ejes, paneles):
        im = ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(titulo)
        ax.axis("off")
        fig.colorbar(im, ax=ax, shrink=0.6)
    fig.suptitle(f"Las Lajas, periodo {periodo}")
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def figura_observado(obs, en_corredor, periodo, fecha_despues, ruta):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    f, c = recorte(en_corredor)
    fig, ax = plt.subplots(figsize=(8, 9))
    rgb = S2_DIR / f"s2_{fecha_despues}_rgb.png"
    if rgb.exists():
        ax.imshow(plt.imread(rgb)[f, c])
    colores = ListedColormap(["#00000000", "#f2c14e", "#d1495b"])
    clases = np.ma.masked_where((obs[f, c] == SIN_DATO) | (obs[f, c] == 0), obs[f, c])
    ax.imshow(clases, cmap=colores, vmin=0, vmax=2, interpolation="nearest")
    ax.contour(en_corredor[f, c], levels=[0.5], colors="w", linewidths=0.8)
    ax.legend(handles=[Patch(color="#d1495b", label="2 – cambio seguro"),
                       Patch(color="#f2c14e", label="1 – posible"),
                       Patch(facecolor="none", edgecolor="w", label="corredor (500 m)")],
              loc="upper right", facecolor="0.3", labelcolor="w")
    ax.set_title(f"Observado en Las Lajas, periodo {periodo} (30 m)")
    ax.axis("off")
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def figura_histogramas(datos, ruta):
    import matplotlib.pyplot as plt

    fig, ejes = plt.subplots(1, 2, figsize=(12, 4))
    for periodo, (ndvi_a, ndvi_d, validos) in datos.items():
        ejes[0].hist(ndvi_a[validos], bins=100, range=(-0.3, 1), histtype="step",
                     label=f"{periodo} antes")
        ejes[0].hist(ndvi_d[validos], bins=100, range=(-0.3, 1), histtype="step",
                     label=f"{periodo} después")
        ejes[1].hist((ndvi_a - ndvi_d)[validos], bins=100, range=(-0.8, 0.8),
                     histtype="step", label=periodo)
    for x in (NDVI_DESNUDO, NDVI_VEGETACION):
        ejes[0].axvline(x, color="k", ls="--", lw=0.8)
    ejes[1].axvline(DELTA_NDVI, color="k", ls="--", lw=0.8)
    ejes[0].set_title("NDVI dentro del corredor")
    ejes[1].set_title("ΔNDVI dentro del corredor")
    for ax in ejes:
        ax.set_yscale("log")
        ax.legend()
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--periodo", nargs="+", default=list(PERIODOS), choices=PERIODOS)
    args = parser.parse_args()

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    en_corredor, junto = corredor()
    a_10m = lambda m: np.repeat(np.repeat(m, FACTOR, 0), FACTOR, 1)  # noqa: E731
    corredor_10m, junto_10m = a_10m(en_corredor), a_10m(junto)
    hist = {}
    for periodo in args.periodo:
        antes, despues = PERIODOS[periodo]
        ndvi_a, val_a = leer_fecha(antes)
        ndvi_d, val_d = leer_fecha(despues)
        if ndvi_a.shape != corredor_10m.shape:
            raise ValueError(f"Sentinel-2 {ndvi_a.shape} no calza con la cuadrícula del DEM × 3")
        valido = val_a & val_d

        clases = quitar_manchas(clasificar(ndvi_a, ndvi_d, valido, corredor_10m), ndvi_d, junto_10m)
        obs = a_30m(clases)
        ruta = PROCESSED / f"observado_lajas_2019_{periodo}.tif"
        guardar(obs, ruta)

        km2 = {c: (obs == c).sum() * RES_DEM**2 / 1e6 for c in (0, 1, 2, SIN_DATO)}
        sin_dato = 1 - (obs[en_corredor] != SIN_DATO).mean()
        print(f"[{periodo}] {antes} → {despues}: clase 2 {km2[2]:.2f} km², "
              f"clase 1 {km2[1]:.2f} km², clase 0 {km2[0]:.2f} km²; "
              f"sin dato dentro del corredor: {sin_dato:.0%}")

        fechas = (f"{antes[:4]}-{antes[4:6]}-{antes[6:]}", f"{despues[:4]}-{despues[4:6]}-{despues[6:]}")
        figura_ndvi(ndvi_a, ndvi_d, en_corredor, periodo, fechas, SALIDA_DIR / f"ndvi_{periodo}.png")
        figura_observado(obs, en_corredor, periodo, despues, SALIDA_DIR / f"observado_{periodo}.png")
        hist[periodo] = (ndvi_a, ndvi_d, valido & corredor_10m)
        print(f"  {ruta}")

    figura_histogramas(hist, SALIDA_DIR / "histogramas.png")
    print(f"Figuras en {SALIDA_DIR}")


if __name__ == "__main__":
    main()
