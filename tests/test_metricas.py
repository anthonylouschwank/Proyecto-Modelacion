"""Pruebas de las métricas de validación con círculos inventados."""

import numpy as np
import pandas as pd
import pytest

from src.config import AOI, RES_DEM
from src.validacion.metricas import (
    alcance_m, confusion, error_alcance, evaluar, fuera_del_corredor, jaccard, puntos_clave,
)

N = 401
FILAS, COLS = np.mgrid[0:N, 0:N]
TODOS = np.ones((N, N), dtype=bool)


def circulo(fila, col, radio):
    return (FILAS - fila) ** 2 + (COLS - col) ** 2 <= radio ** 2


def test_circulos_identicos():
    c = circulo(200, 200, 50)
    assert jaccard(c, c, TODOS) == 1


def test_sin_traslape():
    assert jaccard(circulo(100, 100, 30), circulo(300, 300, 30), TODOS) == 0


def test_mitad_de_area():
    grande = circulo(200, 200, 100)
    chico = circulo(200, 200, 100 / np.sqrt(2))
    assert jaccard(chico, grande, TODOS) == pytest.approx(0.5, abs=0.01)


def test_clase_1_no_cuenta_en_la_estricta():
    sim = circulo(200, 200, 50)
    obs = np.where(sim, 2, 0).astype(np.uint8)
    base = evaluar(sim, obs, np.zeros((N, N)))
    # Un anillo de clase 1 alrededor: la estricta no cambia, la amplia sí empeora.
    obs[circulo(200, 200, 70) & ~sim] = 1
    con_anillo = evaluar(sim, obs, np.zeros((N, N)))
    # VN sí baja, porque las celdas de clase 1 dejan de ser válidas.
    for clave in ("jaccard", "VP", "FP", "FN", "F1", "error_alcance_m"):
        assert con_anillo["estricta"][clave] == base["estricta"][clave]
    assert con_anillo["amplia"]["jaccard"] < base["amplia"]["jaccard"]


def test_confusion():
    sim = np.array([True, True, False, False])
    obs = np.array([True, False, True, False])
    m = confusion(sim, obs, np.ones(4, dtype=bool))
    assert (m["VP"], m["FP"], m["FN"], m["VN"]) == (1, 1, 1, 1)
    assert m["precision"] == m["sensibilidad"] == m["F1"] == 0.5


def test_alcance_en_linea_recta():
    # Cauce recto hacia el sur: la distancia por el cauce crece 30 m por fila.
    distancia = np.full((N, N), np.nan)
    distancia[:, 200] = np.arange(N) * 30.0
    sim = np.zeros((N, N), dtype=bool)
    obs = np.zeros((N, N), dtype=bool)
    sim[:101, 200] = True
    obs[:81, 200] = True
    assert alcance_m(sim, distancia) == 3000
    assert error_alcance(sim, obs, distancia) == 600
    assert alcance_m(np.zeros((N, N), dtype=bool), distancia) == 0


def test_fuera_del_corredor():
    sim = np.zeros((N, N), dtype=bool)
    sim[0, :4] = True
    obs = np.zeros((N, N), dtype=np.uint8)
    obs[0, 0] = 255
    assert fuera_del_corredor(sim, obs) == 0.25


def test_puntos_clave():
    prob = np.zeros((1280, 1280))
    prob[10, 20] = 0.8
    puntos = pd.DataFrame({
        "nombre": ["adentro", "afuera", "fuera_de_la_zona"],
        "x": [AOI[0] + 20 * RES_DEM + 5, AOI[0] + 5, AOI[0] - 100],
        "y": [AOI[3] - 10 * RES_DEM - 5, AOI[3] - 5, AOI[3]],
    })
    r = puntos_clave(prob, puntos)
    assert list(r["alcanzado"]) == [True, False, False]
    assert (r.loc[0, "fila"], r.loc[0, "col"]) == (10, 20)
    assert np.isnan(r.loc[2, "valor"])
