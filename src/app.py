"""Simulador interactivo de lahares en Las Lajas, en el navegador.

Pestaña 1: una corrida del autómata con los controles de la barra lateral
(versión, lluvia, C, Cs, τy, relajación). Pestaña 2: los mapas de
probabilidad del Monte Carlo de 500 corridas ya calculados.

Uso:
    streamlit run src/app.py        # abre http://localhost:8501

Necesita los datos del pipeline del README (data/processed/ y results/montecarlo/).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import streamlit as st

# `streamlit run` ejecuta el archivo como script: hace falta la raíz en el path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import AOI, DATA, PROCESSED, RAIZ, RES_DEM  # noqa: E402
from src.inputs.volumen import area_escurrimiento, volumen_lahar  # noqa: E402
from src.modelo.automata import Parametros, simular  # noqa: E402
from src.modelo.terreno import cargar_dem  # noqa: E402
from src.validacion.metricas import evaluar, puntos_clave  # noqa: E402

MONTECARLO = RAIZ / "results" / "montecarlo"
CALIBRADOS = RAIZ / "results" / "modelo" / "parametros_calibrados.json"


@st.cache_resource
def datos():
    """Todo lo que no cambia entre corridas, cargado una sola vez."""
    from matplotlib.colors import LightSource

    dem = cargar_dem()
    fuente = json.loads((PROCESSED / "lajas_fuente.json").read_text())
    with rasterio.open(PROCESSED / "lajas_cauce_distancia.tif") as src:
        distancia = src.read(1)
    obs = {}
    for p in ("p1", "p2"):
        with rasterio.open(PROCESSED / f"observado_lajas_2019_{p}.tif") as src:
            obs[p] = src.read(1)
    tormentas = pd.read_csv(MONTECARLO / "tormentas_2019.csv")
    sombra = LightSource(315, 45).hillshade(dem, vert_exag=2, dx=RES_DEM, dy=RES_DEM)
    # Compila el autómata con Numba antes de la primera corrida del usuario.
    simular(dem[:50, :50], (25, 25), 1e3, Parametros(max_pasos=10), version="v2")
    return dict(dem=dem, fuente=fuente, distancia=distancia, obs=obs, tormentas=tormentas,
                sombra=sombra, area=area_escurrimiento(fuente),
                puntos=pd.read_csv(DATA / "puntos_clave.csv"),
                calibrados=json.loads(CALIBRADOS.read_text()))


def recorte(mascara, margen=40):
    filas, cols = np.nonzero(mascara)
    return (slice(max(filas.min() - margen, 0), filas.max() + margen),
            slice(max(cols.min() - margen, 0), cols.max() + margen))


def extension(f, c):
    xmin, ymax = AOI[0], AOI[3]
    return (xmin + c.start * RES_DEM, xmin + c.stop * RES_DEM,
            ymax - f.stop * RES_DEM, ymax - f.start * RES_DEM)


def dibujar(d, capa, titulo, etiqueta, norma=None, cmap="inferno_r", con_puntos=True):
    import matplotlib.pyplot as plt

    f, c = recorte(capa > 0)
    ext = extension(f, c)
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.imshow(d["sombra"][f, c], cmap="gray", extent=ext)
    im = ax.imshow(np.ma.masked_less_equal(capa[f, c], 0), cmap=cmap, norm=norma,
                   extent=ext, alpha=0.85)
    fig.colorbar(im, ax=ax, shrink=0.6, label=etiqueta)
    ax.plot(d["fuente"]["x"], d["fuente"]["y"], "c*", ms=14, mec="k", label="Fuente")
    if con_puntos:
        for _, p in d["puntos"].iterrows():
            if ext[0] <= p["x"] <= ext[1] and ext[2] <= p["y"] <= ext[3]:
                ax.plot(p["x"], p["y"], "wo", ms=5, mec="k")
                ax.annotate(p["nombre"], (p["x"], p["y"]), xytext=(4, 4),
                            textcoords="offset points", fontsize=7, color="w")
    ax.set_title(titulo)
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    ax.legend(loc="upper right")
    return fig


def corrida(d):
    st.sidebar.header("Modelo")
    version = st.sidebar.radio("Versión", ["v2", "v1"], horizontal=True,
                               help="v1: sin resistencia (como agua). v2: Bingham calibrada.")

    st.sidebar.header("Lluvia y volumen")
    t = d["tormentas"]
    opciones = {"Tormenta mayor de p1 (61 mm)": float(t[t.periodo == "p1"].lluvia_mm.max()),
                "Tormenta mayor de p2 (150 mm)": float(t[t.periodo == "p2"].lluvia_mm.max()),
                "Elegir a mano": None}
    eleccion = st.sidebar.selectbox("Tormenta", list(opciones), index=1)
    lluvia = opciones[eleccion]
    if lluvia is None:
        lluvia = st.sidebar.slider("Lluvia de la tormenta (mm)", 10.0, 250.0, 80.0, 5.0)
    C = st.sidebar.slider("C – escurrimiento", 0.3, 0.7, 0.5, 0.05)
    Cs = st.sidebar.slider("Cs – sedimento", 0.3, 0.6, 0.45, 0.05)
    volumen = volumen_lahar(lluvia, d["area"], C, Cs)

    cal = d["calibrados"]
    tau_y, relajacion = cal["tau_y"], cal["relajacion"]
    if version == "v2":
        st.sidebar.header("Resistencia del lodo")
        tau_y = st.sidebar.slider("τy – esfuerzo de fluencia (Pa)", 50, 5000,
                                  int(cal["tau_y"]), 50, help="Calibrado con p1: 1000 Pa")
        relajacion = st.sidebar.slider("Relajación", 0.1, 0.9, cal["relajacion"], 0.05)
    # v1 no se detiene sola: se corta en 4000 pasos para que la demo responda rápido.
    params = Parametros(relajacion=relajacion, tau_y=tau_y if version == "v2" else 0.0,
                        max_pasos=20_000 if version == "v2" else 4_000)

    t0 = time.perf_counter()
    with st.spinner("Simulando…"):
        r = simular(d["dem"], (d["fuente"]["fila"], d["fuente"]["col"]), volumen, params,
                    version=version)
    seg = time.perf_counter() - t0

    dist = d["distancia"][r.alcanzado & np.isfinite(d["distancia"])]
    alcance = dist.max() / 1000 if dist.size else 0.0
    k = st.columns(4)
    k[0].metric("Volumen", f"{volumen / 1e6:.2f} millones m³")
    k[1].metric("Alcance por el cauce", f"{alcance:.1f} km")
    k[2].metric("Área con lodo", f"{r.alcanzado.sum() * RES_DEM**2 / 1e6:.2f} km²")
    k[3].metric("Salió de la zona", f"{r.volumen_perdido / volumen:.0%}")
    st.caption(f"{r.pasos} pasos en {seg:.1f} s · confluencia con el Guacalate en el km "
               f"{d['fuente']['km_confluencia']} · puente RN-14 en el km 5.9")

    from matplotlib.colors import LogNorm
    izq, der = st.columns([3, 2])
    with izq:
        fig = dibujar(d, np.where(r.alcanzado, r.h_max, 0),
                      f"{version} – espesor máximo de lodo", "Espesor máximo (m)",
                      norma=LogNorm(0.1, max(r.h_max.max(), 1)))
        st.pyplot(fig)
    with der:
        st.subheader("Contra Sentinel-2 (versión amplia)")
        filas = []
        for p in ("p1", "p2"):
            m = evaluar(r.alcanzado, d["obs"][p], d["distancia"])
            filas.append({"periodo": p, "Jaccard": m["amplia"]["jaccard"],
                          "Jaccard penalizado": m["amplia"]["jaccard_penalizado"],
                          "F1": m["amplia"]["F1"], "fuera del corredor": m["fuera_del_corredor"]})
        st.dataframe(pd.DataFrame(filas).round(3), hide_index=True)
        st.subheader("Puntos clave")
        pc = puntos_clave(r.alcanzado.astype(float), d["puntos"], 0.5)
        st.dataframe(pc[["nombre", "tipo", "alcanzado"]], hide_index=True)


def montecarlo(d):
    st.write("Probabilidad de alcance con 500 corridas por periodo: cada corrida sortea C, "
             "Cs, factor de lluvia, relajación y τy (± 30 % de lo calibrado).")
    periodo = st.radio("Periodo", ["p2", "p1"], horizontal=True)
    with rasterio.open(MONTECARLO / f"prob_{periodo}.tif") as src:
        prob = src.read(1)
    m = pd.read_csv(MONTECARLO / f"muestras_{periodo}.csv")
    k = st.columns(3)
    k[0].metric("Área con P ≥ 0.5", f"{(prob >= 0.5).sum() * RES_DEM**2 / 1e6:.2f} km²")
    k[1].metric("Alcance mediano", f"{m['alcance_cauce_m'].median() / 1000:.1f} km")
    k[2].metric("Volumen sorteado", f"{m['volumen_m3'].min() / 1e6:.1f}–"
                f"{m['volumen_m3'].max() / 1e6:.1f} millones m³")
    izq, der = st.columns([3, 2])
    with izq:
        st.pyplot(dibujar(d, prob, f"Probabilidad de alcance – {periodo} 2019",
                          "Probabilidad de alcance", cmap="magma_r"))
    with der:
        st.subheader("Puntos clave")
        pc = puntos_clave(prob, d["puntos"], 0.5)
        st.dataframe(pc[["nombre", "tipo", "valor"]].rename(columns={"valor": "P"}).round(2),
                     hide_index=True)
        st.image(str(MONTECARLO / "convergencia.png"), caption="Convergencia del Monte Carlo")


def main():
    st.set_page_config(page_title="Lahares en Las Lajas", layout="wide")
    st.title("Simulación de lahares en la barranca Las Lajas, Volcán de Fuego")
    d = datos()
    una, mc = st.tabs(["Una corrida", "Monte Carlo (500 corridas)"])
    with una:
        corrida(d)
    with mc:
        montecarlo(d)


main()
