"""Demo del proyecto en cuatro pasos, con ventanas que muestran el lahar en movimiento.

1. Pruebas automáticas (pytest).
2. Un lahar de la tormenta mayor de p2 con v1 (sin resistencia) y v2 (Bingham
   calibrada), animado a partir del paso en que el lodo llega a cada celda.
3. Monte Carlo corto en vivo: el mapa de probabilidad se actualiza con cada corrida.
4. Validación del Monte Carlo de 500 corridas contra Sentinel-2, puntos clave
   y el mapa de amenaza del INSIVUMEH.

No modifica nada de results/: todo se calcula en memoria. Necesita los datos que
dejan los pasos del pipeline del README (data/processed/ y results/montecarlo/*.tif).

Uso:
    python -m src.demo_video                  # pausa con Enter entre pasos
    python -m src.demo_video --sin-pausas
    python -m src.demo_video --desde 3        # empezar en el Monte Carlo
    python -m src.demo_video --corridas 100 --procesos 8
"""

import argparse
import json
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import rasterio

from src.config import DATA, PROCESSED, RAIZ, RES_DEM
from src.inputs.volumen import cargar_fuente
from src.modelo.automata import Parametros, simular
from src.modelo.terreno import cargar_dem
from src.montecarlo.correr import monte_carlo
from src.montecarlo.rangos import RANGOS
from src.validacion.metricas import evaluar, puntos_clave

MODELO = RAIZ / "results" / "modelo"
MONTECARLO = RAIZ / "results" / "montecarlo"
VALIDACION = RAIZ / "results" / "validacion"
CUADROS = 120


def leer(ruta):
    with rasterio.open(ruta) as src:
        return src.read(1)


def titulo(n, texto):
    print(f"\n{'=' * 70}\n  Paso {n}. {texto}\n{'=' * 70}")


def pausa(activa):
    if activa:
        input("\n[Enter para seguir] ")


def recorte(mascara, margen=30):
    filas, cols = np.nonzero(mascara)
    return (slice(max(filas.min() - margen, 0), filas.max() + margen),
            slice(max(cols.min() - margen, 0), cols.max() + margen))


def sombra(dem):
    from matplotlib.colors import LightSource
    return LightSource(315, 45).hillshade(dem, vert_exag=2, dx=RES_DEM, dy=RES_DEM)


def pruebas():
    titulo(1, "Pruebas automáticas")
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=RAIZ)


def animar_versiones(dem, fuente, distancia):
    """Corre v1 y v2 con el mismo volumen y anima cómo avanza el frente de lodo."""
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    titulo(2, "Un lahar: v1 sin resistencia contra v2 con Bingham")
    tormentas = pd.read_csv(MONTECARLO / "tormentas_2019.csv")
    t = tormentas[tormentas["periodo"] == "p2"].loc[lambda d: d["lluvia_mm"].idxmax()]
    volumen = float(t["volumen_central_m3"])
    cal = json.loads((MODELO / "parametros_calibrados.json").read_text())
    print(f"Tormenta mayor de p2: {t['lluvia_mm']:.0f} mm el {t['inicio'][:10]} "
          f"→ {volumen:.2e} m³ de lodo")

    # v1 no se detiene nunca (20 000 pasos, ~6 min), así que se corta en el paso en
    # que v2 se detiene: la comparación es al mismo tiempo de simulación.
    corridas = {}
    for version in ("v2", "v1"):
        if version == "v2":
            params = Parametros(relajacion=cal["relajacion"], tau_y=cal["tau_y"])
        else:
            params = Parametros(relajacion=cal["relajacion"], max_pasos=corridas["v2"].pasos)
        inicio = time.perf_counter()
        r = simular(dem, fuente, volumen, params, version=version, res=float(RES_DEM))
        d = distancia[r.alcanzado & np.isfinite(distancia)]
        estado = "se detuvo" if r.convergio else "sigue avanzando, se corta aquí"
        print(f"  {version}: {r.pasos} pasos en {time.perf_counter() - inicio:.1f} s ({estado}), "
              f"alcance por el cauce {d.max() / 1000:.1f} km")
        corridas[version] = r
    corridas = {"v1": corridas["v1"], "v2": corridas["v2"]}

    filas, cols = recorte(corridas["v1"].alcanzado | corridas["v2"].alcanzado)
    fondo = sombra(dem)[filas, cols]
    ultimo = max(r.pasos for r in corridas.values())
    pasos = np.unique(np.geomspace(1, ultimo, CUADROS).astype(int))

    from scipy.ndimage import minimum_filter

    fig, ejes = plt.subplots(1, 2, figsize=(10, 9))
    capas = {}
    for ax, (version, r) in zip(ejes, corridas.items()):
        ax.imshow(fondo, cmap="gray")
        # El cauce mide 1–3 celdas de ancho: se engrosa solo para que se vea en pantalla.
        llegada = r.paso_llegada[filas, cols].astype(float)
        llegada[llegada < 0] = np.inf
        llegada = np.ma.masked_invalid(minimum_filter(llegada, size=5))
        capas[version] = (ax.imshow(np.ma.masked_all(llegada.shape), cmap="plasma",
                                    vmin=0, vmax=ultimo, alpha=0.85), llegada)
        ax.plot(fuente[1] - cols.start, fuente[0] - filas.start, "c*", ms=14, mec="k")
        ax.set_axis_off()
    nombres = {"v1": "v1 sin resistencia", "v2": f"v2 Bingham, τy = {cal['tau_y']:.0f} Pa"}

    def cuadro(paso):
        for version, (img, llegada) in capas.items():
            img.set_data(np.ma.masked_where(llegada > paso, llegada))
            r = corridas[version]
            alcanzado = (r.paso_llegada >= 0) & (r.paso_llegada <= paso)
            d = distancia[alcanzado & np.isfinite(distancia)]
            km = d.max() / 1000 if d.size else 0.0
            img.axes.set_title(f"{nombres[version]}\npaso {min(paso, r.pasos)} · {km:.1f} km por el cauce")
        return [img for img, _ in capas.values()]

    fig.suptitle("Avance del lodo en Las Lajas, tormenta mayor de p2", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    animacion = FuncAnimation(fig, cuadro, frames=pasos, interval=60, repeat=False)  # noqa: F841
    plt.show()


def monte_carlo_en_vivo(dem, n, procesos):
    """Monte Carlo de v2 en p2; la ventana se actualiza después de cada corrida."""
    import matplotlib.pyplot as plt

    titulo(3, f"Monte Carlo en vivo: {n} corridas de v2 en p2")
    print("Cada corrida sortea C, Cs, factor de lluvia, relajación y τy:")
    for k, (a, b) in RANGOS.items():
        print(f"  {k:<14} {a:g} – {b:g}")

    ref = leer(MONTECARLO / "prob_p2.tif")
    filas, cols = recorte(ref > 0)
    plt.ion()
    fig, ax = plt.subplots(figsize=(7, 9))
    ax.imshow(sombra(dem)[filas, cols], cmap="gray")
    img = ax.imshow(np.ma.masked_all(ref[filas, cols].shape), cmap="magma_r",
                    vmin=0, vmax=1, alpha=0.85)
    fig.colorbar(img, ax=ax, shrink=0.6, label="Probabilidad de alcance")
    ax.set_axis_off()

    def al_avanzar(i, contador):
        prob = contador[filas, cols] / i
        img.set_data(np.ma.masked_equal(prob, 0))
        ax.set_title(f"Monte Carlo v2, p2: corrida {i} de {n}")
        plt.pause(0.001)

    inicio = time.perf_counter()
    prob, muestras = monte_carlo("p2", n, RANGOS, simulador=simular, version="v2",
                                 procesos=procesos, al_avanzar=al_avanzar)
    print(f"\n{n} corridas en {time.perf_counter() - inicio:.0f} s")
    print(f"  volumen sorteado: {muestras['volumen_m3'].min():.1e} – {muestras['volumen_m3'].max():.1e} m³")
    print(f"  área con P ≥ 0.5: {(prob >= 0.5).sum() * RES_DEM**2 / 1e6:.2f} km² "
          f"(con 500 corridas: {(ref >= 0.5).sum() * RES_DEM**2 / 1e6:.2f} km²)")
    plt.ioff()
    plt.show()


def validacion(distancia):
    import matplotlib.pyplot as plt

    titulo(4, "Validación del Monte Carlo de 500 corridas")
    print("Mapa con P ≥ 0.5 contra el cauce desnudo que ve Sentinel-2:")
    for periodo, uso in (("p1", "calibración"), ("p2", "prueba")):
        sim = leer(MONTECARLO / f"prob_{periodo}.tif") >= 0.5
        obs = leer(PROCESSED / f"observado_lajas_2019_{periodo}.tif")
        m = evaluar(sim, obs, distancia)["amplia"]
        print(f"  {periodo} ({uso:<11}) F1 {m['F1']:.2f}  precisión {m['precision']:.2f}  "
              f"sensibilidad {m['sensibilidad']:.2f}  Jaccard penalizado {m['jaccard_penalizado']:.2f}")

    puntos = pd.read_csv(DATA / "puntos_clave.csv")
    r = puntos_clave(leer(MONTECARLO / "prob_p2.tif"), puntos)
    print("\nPuntos clave en p2:")
    for _, p in r.iterrows():
        print(f"  {p['nombre']:<26} {p['tipo']:<16} P = {p['valor']:.2f}")

    ins = pd.read_csv(VALIDACION / "insivumeh.csv").iloc[0]
    print(f"\nINSIVUMEH: el {ins['sim_dentro_de_zona']:.0%} del lodo simulado cae dentro de su zona de amenaza")

    fig, ejes = plt.subplots(1, 2, figsize=(11, 8))
    for ax, nombre, texto in zip(ejes, ("sim_vs_obs_p2.png", "insivumeh_vs_modelo.png"),
                                 ("Modelo contra Sentinel-2 (p2)", "Modelo contra INSIVUMEH")):
        ax.imshow(plt.imread(VALIDACION / nombre))
        ax.set_title(texto)
        ax.set_axis_off()
    fig.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sin-pausas", action="store_true")
    parser.add_argument("--desde", type=int, default=1, choices=[1, 2, 3, 4])
    parser.add_argument("--corridas", type=int, default=60)
    parser.add_argument("--procesos", type=int, default=8)
    args = parser.parse_args()
    con_pausa = not args.sin_pausas

    dem = cargar_dem()
    f = cargar_fuente()
    fuente = (f["fila"], f["col"])
    distancia = leer(PROCESSED / "lajas_cauce_distancia.tif")

    pasos = {1: pruebas,
             2: lambda: animar_versiones(dem, fuente, distancia),
             3: lambda: monte_carlo_en_vivo(dem, args.corridas, args.procesos),
             4: lambda: validacion(distancia)}
    for n in range(args.desde, 5):
        pasos[n]()
        if n < 4:
            pausa(con_pausa)


if __name__ == "__main__":
    main()
