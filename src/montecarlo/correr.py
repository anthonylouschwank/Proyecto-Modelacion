"""Monte Carlo: mapa de probabilidad de alcance de lahares en Las Lajas.

Cada corrida sortea C, Cs, factor_lluvia, relajacion y tau_y (uniformes en
RANGOS), toma la tormenta más grande del periodo, calcula su volumen con
`volumen_lahar` y corre `simular`. La probabilidad de cada celda es la
fracción de corridas en que fue alcanzada.

¿Por qué solo la tormenta más grande? Con la misma fuente y los mismos
parámetros, un volumen mayor cubre todo lo que cubre uno menor, así que la
unión de las huellas de todas las tormentas ≈ la huella de la mayor.

Mientras el modelo de P1 no sea rápido y no se detenga solo (v2), se usa un
stub: un círculo alrededor de la fuente con radio proporcional a V^(1/3).

Uso:
    python -m src.montecarlo.correr --n 20                      # stub, p1 y p2
    python -m src.montecarlo.correr --n 500 --simulador automata --version v2 --procesos 6
       (rangos de relajacion y tau_y: ± 30 % de lo calibrado, ver rangos.py)

Requiere antes: python -m src.inputs.cuenca  y  la lluvia de 2019 (ver src.inputs.volumen).

Salidas en results/montecarlo/:
    prob_<periodo>.tif, prob_<periodo>.png, muestras_<periodo>.csv, convergencia.png
"""

import argparse
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
import pandas as pd
import rasterio

from src.config import PROCESSED, RAIZ, RAW, RES_DEM
from src.inputs.volumen import (
    area_escurrimiento, cargar_fuente, cargar_lluvia, tormentas, volumen_lahar,
)
from src.modelo.automata import Parametros, simular
from src.modelo.terreno import cargar_dem
from src.montecarlo.rangos import RANGOS  # rangos y sus fuentes

DEM = RAW / "dem" / "dem_fuego_30m.tif"
SALIDA_DIR = RAIZ / "results" / "montecarlo"

# Stub: radio (m) = K_STUB · V^(1/3). Con V = 4·10⁴ m³ da ~680 m.
K_STUB = 20.0


@dataclass
class ResultadoStub:
    alcanzado: np.ndarray


def simular_stub(dem, fuente, volumen_m3, params=None, version="v1", res=30.0):
    """Misma firma que `src.modelo.automata.simular`: un círculo alrededor de la fuente."""
    radio = K_STUB * volumen_m3 ** (1 / 3) / res  # en celdas
    filas, cols = np.ogrid[:dem.shape[0], :dem.shape[1]]
    return ResultadoStub(alcanzado=np.hypot(filas - fuente[0], cols - fuente[1]) <= radio)


SIMULADORES = {"stub": simular_stub, "automata": simular}


def tormenta_mayor(periodo):
    t = tormentas(cargar_lluvia())
    t = t[t["periodo"] == periodo]
    if t.empty:
        raise ValueError(f"No hay tormentas en el periodo {periodo}")
    return t.loc[t["lluvia_mm"].idxmax()]


# Estado de cada proceso (se carga una vez, no en cada corrida).
_ESTADO = {}


def _iniciar(simulador, version):
    # El autómata corre sobre el DEM sin hoyos (ver src/modelo/terreno.py).
    _ESTADO["dem"] = cargar_dem()
    f = cargar_fuente()
    _ESTADO.update(fuente=(f["fila"], f["col"]), simulador=simulador, version=version)


def _corrida(args):
    volumen, relajacion, tau_y = args
    params = Parametros(relajacion=relajacion, tau_y=tau_y)
    r = _ESTADO["simulador"](_ESTADO["dem"], _ESTADO["fuente"], volumen, params,
                             version=_ESTADO["version"], res=float(RES_DEM))
    return r.alcanzado


def monte_carlo(periodo: str, n: int, rangos: dict, semilla: int = 42,
                simulador=simular_stub, version="v1", procesos=1,
                al_avanzar=None) -> tuple[np.ndarray, pd.DataFrame]:
    """Devuelve (prob, muestras):
    prob: (1280, 1280) float, fracción de corridas en que cada celda fue alcanzada.
    muestras: una fila por corrida con los parámetros sorteados y el alcance obtenido.

    `al_avanzar(i, contador)` se llama después de cada corrida (i empieza en 1).
    """
    area = area_escurrimiento()
    tormenta = tormenta_mayor(periodo)
    with rasterio.open(PROCESSED / "lajas_cauce_distancia.tif") as src:
        distancia = src.read(1)

    # Todos los sorteos van primero, así el resultado no depende del número de procesos.
    rng = np.random.default_rng(semilla)
    muestras = pd.DataFrame({k: rng.uniform(a, b, n) for k, (a, b) in rangos.items()})
    muestras.insert(0, "corrida", np.arange(1, n + 1))
    muestras["lluvia_mm"] = tormenta["lluvia_mm"] * muestras["factor_lluvia"]
    muestras["volumen_m3"] = [
        volumen_lahar(p, area, c, cs)
        for p, c, cs in zip(muestras["lluvia_mm"], muestras["C"], muestras["Cs"])
    ]
    tareas = list(zip(muestras["volumen_m3"], muestras["relajacion"], muestras["tau_y"]))

    contador = np.zeros(distancia.shape, dtype="int32")
    area_km2, alcance = [], []

    def registrar(i, alcanzado):
        contador[alcanzado] += 1
        area_km2.append(alcanzado.sum() * RES_DEM**2 / 1e6)
        en_cauce = distancia[alcanzado]
        alcance.append(float(np.nanmax(en_cauce)) if np.isfinite(en_cauce).any() else np.nan)
        if al_avanzar:
            al_avanzar(i, contador)

    if procesos > 1:
        with ProcessPoolExecutor(procesos, initializer=_iniciar,
                                 initargs=(simulador, version)) as ex:
            for i, alcanzado in enumerate(ex.map(_corrida, tareas), start=1):
                registrar(i, alcanzado)
    else:
        _iniciar(simulador, version)
        for i, t in enumerate(tareas, start=1):
            registrar(i, _corrida(t))

    muestras["area_alcanzada_km2"] = area_km2
    muestras["alcance_cauce_m"] = alcance
    muestras.attrs["tormenta"] = tormenta
    return contador / n, muestras


def guardar_prob(prob, ruta):
    with rasterio.open(DEM) as ref:
        perfil = dict(ref.profile, dtype="float32", nodata=None, compress="deflate")
    with rasterio.open(ruta, "w", **perfil) as dst:
        dst.write(prob.astype("float32"), 1)


def figura_prob(prob, periodo, titulo, ruta):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, ListedColormap

    with rasterio.open(DEM) as src:
        dem = src.read(1)
        b = src.bounds
    with rasterio.open(PROCESSED / "lajas_cauce.tif") as src:
        cauce = src.read(1)
    f = cargar_fuente()

    filas, cols = np.nonzero(prob > 0)
    m = 30
    r0, r1 = max(filas.min() - m, 0), min(filas.max() + m, dem.shape[0])
    c0, c1 = max(cols.min() - m, 0), min(cols.max() + m, dem.shape[1])
    extent = (b.left + c0 * RES_DEM, b.left + c1 * RES_DEM,
              b.top - r1 * RES_DEM, b.top - r0 * RES_DEM)

    sombra = LightSource(315, 45).hillshade(dem, vert_exag=2, dx=RES_DEM, dy=RES_DEM)
    fig, ax = plt.subplots(figsize=(8, 9))
    ax.imshow(sombra[r0:r1, c0:c1], cmap="gray", extent=extent)
    im = ax.imshow(np.ma.masked_equal(prob[r0:r1, c0:c1], 0), cmap="magma_r", vmin=0, vmax=1,
                   extent=extent, alpha=0.8, interpolation="nearest")
    ax.imshow(np.ma.masked_equal(cauce[r0:r1, c0:c1], 0), cmap=ListedColormap(["none", "deepskyblue"]),
              vmin=0, vmax=1, extent=extent, interpolation="nearest", alpha=0.6)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Probabilidad de alcance")
    ax.plot(f["x"], f["y"], "c*", ms=14, mec="k", label="Fuente")
    ax.plot([], [], "-", color="deepskyblue", label="Cauce")
    ax.legend(loc="upper right")
    ax.set_title(titulo)
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    fig.savefig(ruta, dpi=120, bbox_inches="tight")
    plt.close(fig)


def figura_convergencia(curvas, ruta):
    """curvas: {periodo: [(N, dif. máxima, dif. media), …]} entre p(N) y p(N/2)."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for periodo, puntos in curvas.items():
        ns, dmax, dmed = zip(*puntos)
        ax.plot(ns, dmax, "o-", label=f"{periodo}: máx |p(N) − p(N/2)|")
        ax.plot(ns, dmed, "s--", label=f"{periodo}: media en celdas con p > 0")
    ax.set_xscale("log", base=2)
    ax.set_xticks(ns, [str(n) for n in ns])
    ax.set_xlabel("Número de corridas N")
    ax.set_ylabel("Diferencia de probabilidad")
    ax.set_title("Convergencia del Monte Carlo")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.savefig(ruta, dpi=120, bbox_inches="tight")
    plt.close(fig)


def puntos_control(n, minimo=5):
    """N, N/2, N/4, … hasta `minimo` (en orden creciente)."""
    puntos = []
    while n >= minimo:
        puntos.append(n)
        n //= 2
    return sorted(puntos)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--periodo", nargs="+", default=["p1", "p2"], choices=["p1", "p2"])
    parser.add_argument("--n", type=int, default=20, help="número de corridas")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--simulador", default="stub", choices=SIMULADORES)
    parser.add_argument("--version", default="v1", help="versión del autómata de P1")
    parser.add_argument("--procesos", type=int, default=1)
    args = parser.parse_args()

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    simulador = SIMULADORES[args.simulador]
    control = puntos_control(args.n)
    curvas = {}
    for periodo in args.periodo:
        fotos = {}
        t0 = time.perf_counter()

        def al_avanzar(i, contador):
            if i in control:
                fotos[i] = contador / i
            if i % max(args.n // 10, 1) == 0:
                print(f"  {i}/{args.n} corridas ({time.perf_counter() - t0:.0f} s)")

        print(f"[{periodo}] {args.n} corridas con {args.simulador} ({args.version})")
        prob, muestras = monte_carlo(periodo, args.n, RANGOS, args.semilla, simulador,
                                     args.version, args.procesos, al_avanzar)
        t = muestras.attrs["tormenta"]
        print(f"  tormenta mayor: {t['lluvia_mm']:.0f} mm el {t['inicio']:%Y-%m-%d}; "
              f"volumen {muestras['volumen_m3'].min():.2e}–{muestras['volumen_m3'].max():.2e} m³")
        print(f"  área con p > 0: {(prob > 0).sum() * RES_DEM**2 / 1e6:.2f} km²; "
              f"con p >= 0.5: {(prob >= 0.5).sum() * RES_DEM**2 / 1e6:.2f} km²")
        print(f"  alcance por el cauce: mediana {muestras['alcance_cauce_m'].median() / 1000:.2f} km")

        guardar_prob(prob, SALIDA_DIR / f"prob_{periodo}.tif")
        muestras.to_csv(SALIDA_DIR / f"muestras_{periodo}.csv", index=False)
        titulo = (f"Probabilidad de alcance – Las Lajas, {periodo} 2019\n"
                  f"N = {args.n}, {args.simulador} {args.version}, "
                  f"tormenta del {t['inicio']:%d-%m} ({t['lluvia_mm']:.0f} mm)")
        figura_prob(prob, periodo, titulo, SALIDA_DIR / f"prob_{periodo}.png")

        curvas[periodo] = []
        for n in control[1:]:
            dif = np.abs(fotos[n] - fotos[n // 2])
            alguna = (fotos[n] > 0) | (fotos[n // 2] > 0)
            curvas[periodo].append((n, dif.max(), dif[alguna].mean()))

    if any(curvas.values()):
        figura_convergencia(curvas, SALIDA_DIR / "convergencia.png")
    print(f"Guardado en {SALIDA_DIR}")


if __name__ == "__main__":
    main()
