"""Evaluación final: ¿el modelo predice la realidad?

Con los parámetros ya fijos (calibrados con p1), compara:
1. Sentinel-2: el mapa de probabilidad del Monte Carlo con umbral 0.5 contra
   lo observado en p1 (calibración) y p2 (prueba), en versión estricta,
   amplia y amplia penalizada.
2. Puntos clave: la probabilidad en cada punto contra lo esperado.
3. INSIVUMEH (escenario B, lluvias muy intensas): una corrida de volumen alto
   contra la zona de amenaza de Las Lajas, con el traslape en los dos sentidos.

Uso:
    python -m src.validacion.evaluar

Requiere: el Monte Carlo (prob_p1.tif, prob_p2.tif), las máscaras observadas,
src.validacion.mapa_amenaza y results/modelo/parametros_calibrados.json.

Salidas en results/validacion/:
    tabla_metricas.csv, puntos_clave.csv, insivumeh.csv,
    sim_vs_obs_<periodo>.png, insivumeh_vs_modelo.png
"""

import json

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage

from src.config import DATA, PROCESSED, RAIZ, RES_DEM
from src.inputs.volumen import area_escurrimiento, volumen_lahar
from src.modelo.automata import Parametros, simular
from src.modelo.terreno import cargar_dem
from src.montecarlo.rangos import RANGOS
from src.validacion.metricas import clases, evaluar, puntos_clave

SALIDA_DIR = RAIZ / "results" / "validacion"
MONTECARLO = RAIZ / "results" / "montecarlo"
CALIBRADOS = RAIZ / "results" / "modelo" / "parametros_calibrados.json"
UMBRAL = 0.5
ZONA_LAJAS_M = 2000  # la rama de Las Lajas del mapa: amenaza a <= 2 km del cauce


def leer(ruta):
    with rasterio.open(ruta) as src:
        return src.read(1)


def tabla_sentinel(distancia):
    filas = []
    for periodo, uso in (("p1", "calibración"), ("p2", "prueba")):
        prob = leer(MONTECARLO / f"prob_{periodo}.tif")
        obs = leer(PROCESSED / f"observado_lajas_2019_{periodo}.tif")
        sim = prob >= UMBRAL
        m = evaluar(sim, obs, distancia)
        for version in ("estricta", "amplia"):
            v = m[version]
            filas.append({"periodo": periodo, "uso": uso, "version": version,
                          "celdas_observadas": int(clases(obs, version)[0].sum()),
                          "jaccard": v["jaccard"], "jaccard_penalizado": v["jaccard_penalizado"],
                          "F1": v["F1"], "precision": v["precision"],
                          "sensibilidad": v["sensibilidad"], "error_alcance_m": v["error_alcance_m"],
                          "fuera_del_corredor": m["fuera_del_corredor"]})
        figura_confusion(sim, obs, periodo, SALIDA_DIR / f"sim_vs_obs_{periodo}.png")
    return pd.DataFrame(filas)


def tabla_puntos():
    puntos = pd.read_csv(DATA / "puntos_clave.csv")
    salida = puntos[["nombre", "tipo", "esperado_p1", "esperado_p2"]].copy()
    for periodo in ("p1", "p2"):
        r = puntos_clave(leer(MONTECARLO / f"prob_{periodo}.tif"), puntos, UMBRAL)
        salida[f"prob_{periodo}"] = r["valor"].round(3)
        salida[f"alcanzado_{periodo}"] = r["alcanzado"]
        esperado = salida[f"esperado_{periodo}"]
        conocido = esperado.notna()
        salida.loc[conocido, f"resultado_{periodo}"] = np.select(
            [r["alcanzado"][conocido] & (esperado[conocido] == 1),
             r["alcanzado"][conocido] & (esperado[conocido] == 0),
             ~r["alcanzado"][conocido] & (esperado[conocido] == 1)],
            ["acierto", "falsa alarma", "fallo"], default="acierto (no llega)")
    return salida


def comparar_insivumeh(dem, distancia):
    """Corrida de volumen alto vs. la zona de amenaza de Las Lajas del escenario B."""
    fuente = json.loads((PROCESSED / "lajas_fuente.json").read_text())
    tormentas = pd.read_csv(MONTECARLO / "tormentas_2019.csv")
    lluvia = tormentas["lluvia_mm"].max() * RANGOS["factor_lluvia"][1]
    volumen = volumen_lahar(lluvia, area_escurrimiento(fuente), RANGOS["C"][1], RANGOS["Cs"][1])
    cal = json.loads(CALIBRADOS.read_text())
    params = Parametros(relajacion=cal["relajacion"], **{cal["tipo"]: cal[cal["tipo"]]})
    r = simular(dem, (fuente["fila"], fuente["col"]), volumen, params, version="v2")

    amenaza = leer(PROCESSED / "amenaza_insivumeh_B.tif")
    cerca = ndimage.distance_transform_edt(~np.isfinite(distancia)) * RES_DEM <= ZONA_LAJAS_M
    zona = (amenaza > 0) & cerca & (dem < fuente["z"])
    sim = r.alcanzado
    d = distancia[sim & np.isfinite(distancia)]
    fila = {"lluvia_mm": lluvia, "volumen_m3": volumen,
            "area_sim_km2": sim.sum() * RES_DEM**2 / 1e6,
            "area_zona_km2": zona.sum() * RES_DEM**2 / 1e6,
            "alcance_cauce_km": d.max() / 1000 if d.size else 0.0,
            "sim_dentro_de_zona": (sim & zona).sum() / sim.sum(),
            "zona_cubierta_por_sim": (sim & zona).sum() / zona.sum(),
            "zona_alta_cubierta": (sim & zona & (amenaza == 3)).sum() / (zona & (amenaza == 3)).sum()}
    figura_insivumeh(sim, zona, amenaza, SALIDA_DIR / "insivumeh_vs_modelo.png")
    return pd.DataFrame([fila])


def recorte(mascara, margen=25):
    filas, cols = np.nonzero(mascara)
    return (slice(max(filas.min() - margen, 0), filas.max() + margen),
            slice(max(cols.min() - margen, 0), cols.max() + margen))


def figura_confusion(sim, obs, periodo, ruta):
    """Celdas VP / FP / FN contra la versión amplia, y lo que cae fuera del corredor."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    o, validos = clases(obs, "amplia")
    mapa = np.zeros(sim.shape, dtype="uint8")
    mapa[validos] = 1
    mapa[sim & o & validos] = 2
    mapa[sim & ~o & validos] = 3
    mapa[~sim & o & validos] = 4
    mapa[sim & ~validos] = 5
    f, c = recorte(mapa > 1)
    colores = ListedColormap(["#ffffff", "#e8e8e8", "#2a9d8f", "#e76f51", "#264653", "#c9a227"])
    fig, ax = plt.subplots(figsize=(7, 9))
    ax.imshow(mapa[f, c], cmap=colores, vmin=0, vmax=5, interpolation="nearest")
    ax.legend(handles=[Patch(color=colores.colors[k], label=n) for k, n in
                       ((2, "VP: simulado y observado"), (3, "FP: solo simulado"),
                        (4, "FN: solo observado"), (5, "simulado fuera del corredor"),
                        (1, "corredor sin lodo"))], loc="lower left", fontsize=8)
    ax.set_title(f"Modelo (p ≥ {UMBRAL}) vs. Sentinel-2 amplio, {periodo}")
    ax.axis("off")
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def figura_insivumeh(sim, zona, amenaza, ruta):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    mapa = np.zeros(sim.shape, dtype="uint8")
    mapa[zona] = 1
    mapa[zona & (amenaza == 3)] = 2
    mapa[sim & ~zona] = 3
    mapa[sim & zona] = 4
    f, c = recorte(mapa > 0)
    colores = ListedColormap(["#ffffff", "#f6d58e", "#f0a07a", "#264653", "#2a9d8f"])
    fig, ax = plt.subplots(figsize=(7, 9))
    ax.imshow(mapa[f, c], cmap=colores, vmin=0, vmax=4, interpolation="nearest")
    ax.legend(handles=[Patch(color=colores.colors[k], label=n) for k, n in
                       ((1, "amenaza baja/media INSIVUMEH"), (2, "amenaza alta INSIVUMEH"),
                        (4, "modelo dentro de la zona"), (3, "modelo fuera de la zona"))],
              loc="lower left", fontsize=8)
    ax.set_title("Corrida de volumen alto vs. INSIVUMEH escenario B (Las Lajas)")
    ax.axis("off")
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main():
    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    distancia = leer(PROCESSED / "lajas_cauce_distancia.tif")

    sentinel = tabla_sentinel(distancia)
    sentinel.to_csv(SALIDA_DIR / "tabla_metricas.csv", index=False)
    print("Sentinel-2 (prob >= 0.5):")
    print(sentinel.drop(columns=["uso"]).round(3).to_string(index=False))

    puntos = tabla_puntos()
    puntos.to_csv(SALIDA_DIR / "puntos_clave.csv", index=False)
    print("\nPuntos clave:")
    print(puntos.to_string(index=False))

    insivumeh = comparar_insivumeh(cargar_dem(), distancia)
    insivumeh.to_csv(SALIDA_DIR / "insivumeh.csv", index=False)
    print("\nINSIVUMEH escenario B:")
    print(insivumeh.round(3).T.to_string(header=False))
    print(f"\nGuardado en {SALIDA_DIR}")


if __name__ == "__main__":
    main()
