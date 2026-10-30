"""Métricas para comparar lo simulado con lo observado.

Todas las entradas están en la cuadrícula del DEM (ver docs/tareas/00_general.md).
La máscara observada de P3 es uint8 con clases:
    0 = sin cambio, 1 = cambio probable, 2 = cambio seguro, 255 = no válido
    (nube o fuera del corredor de 500 m alrededor del cauce).

Cada métrica se calcula en dos versiones:
    estricta: positivos = clase 2; la clase 1 se ignora (válidos = 0 y 2).
    amplia:   positivos = clases 1 y 2 (válidos = 0, 1 y 2).
"""

import numpy as np
import pandas as pd

from src.config import AOI, RES_DEM

NO_VALIDO = 255
VERSIONES = {
    "estricta": {"positivos": (2,), "validos": (0, 2)},
    "amplia": {"positivos": (1, 2), "validos": (0, 1, 2)},
}


def clases(obs: np.ndarray, version: str) -> tuple[np.ndarray, np.ndarray]:
    """Convierte la máscara de P3 en (observado bool, válidos bool) según la versión."""
    v = VERSIONES[version]
    return np.isin(obs, v["positivos"]), np.isin(obs, v["validos"])


def jaccard(sim, obs, validos) -> float:
    """|S ∩ O| / |S ∪ O| dentro de `validos`. Devuelve NaN si ambas están vacías."""
    s, o = sim & validos, obs & validos
    union = (s | o).sum()
    return float((s & o).sum() / union) if union else float("nan")


def confusion(sim, obs, validos) -> dict:
    """Matriz de confusión celda por celda dentro de `validos`, con precisión, sensibilidad y F1."""
    s, o = sim[validos], obs[validos]
    vp = int((s & o).sum())
    fp = int((s & ~o).sum())
    fn = int((~s & o).sum())
    vn = int((~s & ~o).sum())
    precision = vp / (vp + fp) if vp + fp else float("nan")
    sensibilidad = vp / (vp + fn) if vp + fn else float("nan")
    f1 = 2 * vp / (2 * vp + fp + fn) if vp + fp + fn else float("nan")
    return {"VP": vp, "FP": fp, "FN": fn, "VN": vn,
            "precision": precision, "sensibilidad": sensibilidad, "F1": f1}


def alcance_m(mascara, distancia) -> float:
    """Distancia máxima por el cauce (m) entre las celdas con lodo; 0 si no hay ninguna.

    `distancia` es lajas_cauce_distancia.tif de P2; las celdas sin distancia
    (NaN) no cuentan.
    """
    d = distancia[mascara & np.isfinite(distancia)]
    return float(d.max()) if d.size else 0.0


def error_alcance(sim, obs, distancia) -> float:
    """alcance_sim − alcance_obs en metros (positivo = el modelo llega más lejos)."""
    return alcance_m(sim, distancia) - alcance_m(obs, distancia)


def fuera_del_corredor(sim, obs) -> float:
    """Fracción del área simulada que cae en celdas no válidas (255).

    Los desbordes a más de 500 m del cauce no se penalizan en las otras métricas,
    así que si esta fracción es alta hay un problema.
    """
    total = sim.sum()
    return float((sim & (obs == NO_VALIDO)).sum() / total) if total else 0.0


def evaluar(sim: np.ndarray, obs: np.ndarray, distancia: np.ndarray) -> dict:
    """sim: bool (alcanzado por el modelo). obs: uint8 de P3 (0/1/2/255).
    distancia: lajas_cauce_distancia.tif de P2.
    Devuelve las métricas en sus dos versiones, 'estricta' y 'amplia'."""
    sim = sim.astype(bool)
    resultado = {"fuera_del_corredor": fuera_del_corredor(sim, obs)}
    for version in VERSIONES:
        o, validos = clases(obs, version)
        resultado[version] = {
            "jaccard": jaccard(sim, o, validos),
            **confusion(sim, o, validos),
            "error_alcance_m": error_alcance(sim, o, distancia),
        }
    return resultado


def utm_a_celda(x, y, origen=(AOI[0], AOI[3]), res=RES_DEM):
    """(x, y) en UTM 15N → (fila, col) de la cuadrícula del DEM (fila 0 = norte)."""
    return int((origen[1] - y) // res), int((x - origen[0]) // res)


def puntos_clave(mapa, puntos: pd.DataFrame, umbral=0.5) -> pd.DataFrame:
    """Valor del mapa en cada punto de data/puntos_clave.csv y si se considera alcanzado.

    `mapa` puede ser bool (una corrida) o probabilidad 0–1 (Monte Carlo).
    Los puntos fuera de la cuadrícula quedan con valor NaN y alcanzado = False.
    """
    filas, cols, valores = [], [], []
    for x, y in zip(puntos["x"], puntos["y"]):
        f, c = utm_a_celda(x, y)
        dentro = 0 <= f < mapa.shape[0] and 0 <= c < mapa.shape[1]
        filas.append(f)
        cols.append(c)
        valores.append(float(mapa[f, c]) if dentro else float("nan"))
    salida = puntos.copy()
    salida["fila"], salida["col"], salida["valor"] = filas, cols, valores
    salida["alcanzado"] = salida["valor"] >= umbral
    return salida
