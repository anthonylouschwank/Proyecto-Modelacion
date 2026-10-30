"""Calibración de v2 con el periodo p1 y comparación de versiones.

Búsqueda en cuadrícula de `relajacion` × `h_min` (v2 simple) y `relajacion` ×
`tau_y` (v2 Bingham). Cada combinación se corre con el volumen central de la
tormenta más grande de p1 (la misma suposición del Monte Carlo) y se compara
con observado_lajas_2019_p1.tif.

Objetivo: Jaccard amplio penalizado, |S ∩ O| / (|S ∪ O| + |S fuera del corredor|).
Dentro de Las Lajas casi no hay clase 2 (la barranca está pelada desde 2018),
así que la versión estricta no sirve para calibrar; y el Jaccard amplio normal
ignora el lodo que sale del corredor (al Guacalate), con lo que siempre ganaría
el modelo que llega más lejos.

p2 NO se usa aquí: con los parámetros ya fijos, `--versiones` evalúa v1 y v2
en p1 y p2 (prueba).

Uso:
    python -m src.modelo.calibrar               # calibración con p1
    python -m src.modelo.calibrar --versiones   # tabla v1 vs v2 en p1 y p2

Salidas en results/modelo/:
    calibracion_p1.csv, calibracion_p1.png, parametros_calibrados.json,
    metricas_versiones.csv
"""

import argparse
import json
from itertools import product

import numpy as np
import pandas as pd
import rasterio

from src.config import PROCESSED, RAIZ, RES_DEM
from src.modelo.automata import Parametros, simular
from src.modelo.terreno import cargar_dem
from src.validacion.metricas import evaluar, jaccard_penalizado

SALIDA_DIR = RAIZ / "results" / "modelo"
TORMENTAS = RAIZ / "results" / "montecarlo" / "tormentas_2019.csv"
CALIBRADOS = SALIDA_DIR / "parametros_calibrados.json"

# Los rangos del plan (0.5–5 m, 200–5000 Pa), extendidos hacia abajo.
RELAJACION = (0.2, 0.4, 0.6, 0.8)
H_MIN = (0.1, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0)
TAU_Y = (50, 100, 200, 500, 1000, 2000, 5000)


def cargar_entradas():
    fuente = json.loads((PROCESSED / "lajas_fuente.json").read_text())
    with rasterio.open(PROCESSED / "lajas_cauce_distancia.tif") as src:
        distancia = src.read(1)
    obs = {}
    for p in ("p1", "p2"):
        with rasterio.open(PROCESSED / f"observado_lajas_2019_{p}.tif") as src:
            obs[p] = src.read(1)
    return cargar_dem(), (fuente["fila"], fuente["col"]), distancia, obs


def volumen_periodo(periodo):
    t = pd.read_csv(TORMENTAS)
    t = t[t["periodo"] == periodo]
    return float(t.loc[t["lluvia_mm"].idxmax(), "volumen_central_m3"])


def fila_metricas(r, obs, distancia):
    m = evaluar(r.alcanzado, obs, distancia)
    d = distancia[r.alcanzado & np.isfinite(distancia)]
    fila = {"area_km2": r.alcanzado.sum() * RES_DEM**2 / 1e6,
            "alcance_cauce_km": d.max() / 1000 if d.size else 0.0,
            "pasos": r.pasos, "fuera_del_corredor": m["fuera_del_corredor"]}
    for v in ("estricta", "amplia"):
        for k in ("jaccard", "F1", "precision", "sensibilidad", "error_alcance_m"):
            fila[f"{k}_{v}"] = m[v][k]
    fila["objetivo"] = jaccard_penalizado(r.alcanzado, obs)
    return fila



def calibrar():
    dem, fuente, distancia, obs = cargar_entradas()
    volumen = volumen_periodo("p1")
    print(f"Volumen de la tormenta mayor de p1: {volumen:.3g} m³")
    combinaciones = ([("h_min", rel, v) for rel, v in product(RELAJACION, H_MIN)]
                     + [("tau_y", rel, v) for rel, v in product(RELAJACION, TAU_Y)])
    filas = []
    for i, (tipo, rel, valor) in enumerate(combinaciones, start=1):
        params = Parametros(relajacion=rel, **{tipo: valor})
        r = simular(dem, fuente, volumen, params, version="v2")
        filas.append({"tipo": tipo, "relajacion": rel, "valor": valor,
                      **fila_metricas(r, obs["p1"], distancia)})
        if i % 14 == 0:
            print(f"  {i}/{len(combinaciones)}")
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA_DIR / "calibracion_p1.csv", index=False)

    mejor = tabla.loc[tabla["objetivo"].idxmax()]
    elegidos = {"tipo": mejor["tipo"], "relajacion": float(mejor["relajacion"]),
                mejor["tipo"]: float(mejor["valor"]), "volumen_p1_m3": volumen,
                "objetivo_p1": float(mejor["objetivo"]),
                "jaccard_amplia_p1": float(mejor["jaccard_amplia"])}
    CALIBRADOS.write_text(json.dumps(elegidos, indent=2))
    print("Mejor combinación:", json.dumps(elegidos))
    for tipo in ("h_min", "tau_y"):
        t = tabla[tabla["tipo"] == tipo]
        print(f"  mejor con {tipo}:", t.loc[t["objetivo"].idxmax(),
              ["relajacion", "valor", "objetivo", "jaccard_amplia", "alcance_cauce_km"]].to_dict())
    figura(tabla, SALIDA_DIR / "calibracion_p1.png")


def figura(tabla, ruta):
    import matplotlib.pyplot as plt

    fig, ejes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, (tipo, unidad) in zip(ejes, (("h_min", "m"), ("tau_y", "Pa"))):
        t = tabla[tabla["tipo"] == tipo]
        for rel, g in t.groupby("relajacion"):
            ax.plot(g["valor"], g["objetivo"], "o-", label=f"relajación {rel}")
        ax.set_xscale("log")
        ax.set_xlabel(f"{tipo} ({unidad})")
        ax.set_title(f"v2 – {'espesor mínimo' if tipo == 'h_min' else 'Bingham'}")
        ax.grid(alpha=0.3)
    ejes[0].set_ylabel("Jaccard amplio penalizado, p1")
    ejes[1].legend()
    fig.suptitle("Calibración con p1: sensibilidad del Jaccard a los parámetros")
    fig.savefig(ruta, dpi=120, bbox_inches="tight")
    plt.close(fig)


def comparar_versiones():
    """v1 y v2 calibrada contra p1 (calibración) y p2 (prueba)."""
    dem, fuente, distancia, obs = cargar_entradas()
    elegidos = json.loads(CALIBRADOS.read_text())
    v2 = Parametros(relajacion=elegidos["relajacion"],
                    **{elegidos["tipo"]: elegidos[elegidos["tipo"]]})
    filas = []
    for periodo in ("p1", "p2"):
        volumen = volumen_periodo(periodo)
        for version, params in (("v1", Parametros(relajacion=0.5)), ("v2", v2)):
            r = simular(dem, fuente, volumen, params, version=version)
            filas.append({"version": version, "periodo": periodo, "volumen_m3": volumen,
                          "relajacion": params.relajacion, "h_min": params.h_min,
                          "tau_y": params.tau_y, **fila_metricas(r, obs[periodo], distancia)})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA_DIR / "metricas_versiones.csv", index=False)
    print(tabla[["version", "periodo", "volumen_m3", "alcance_cauce_km", "area_km2",
                 "objetivo", "jaccard_amplia", "F1_amplia", "precision_amplia",
                 "fuera_del_corredor"]].round(3).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--versiones", action="store_true",
                        help="solo comparar v1 y v2 calibrada en p1 y p2")
    args = parser.parse_args()
    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    if not args.versiones:
        calibrar()
    comparar_versiones()


if __name__ == "__main__":
    main()
