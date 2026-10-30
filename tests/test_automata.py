"""Pruebas de cordura del autómata en terrenos inventados."""

import numpy as np
import pytest

from src.modelo.automata import Parametros, simular

RES = 30.0
N = 61
FILAS, COLS = np.mgrid[0:N, 0:N]


def masa(r, res=RES):
    return r.h_final.sum() * res * res + r.volumen_perdido


@pytest.mark.parametrize("pasos_fuente", [1, 50])
def test_conservacion_de_masa(pasos_fuente):
    rng = np.random.default_rng(0)
    dem = rng.uniform(0, 50, (N, N))
    params = Parametros(pasos_fuente=pasos_fuente, max_pasos=500)
    r = simular(dem, (30, 30), 1e5, params)
    assert masa(r) == pytest.approx(1e5, rel=1e-9)


def test_plano_inclinado_baja_por_la_pendiente():
    dem = -FILAS * 3.0  # baja hacia el sur (filas crecientes)
    r = simular(dem, (5, 30), 5e4, Parametros(max_pasos=300))
    filas_con_lodo = np.nonzero(r.alcanzado)[0]
    assert filas_con_lodo.max() > 20          # avanzó cuesta abajo
    assert filas_con_lodo.min() >= 4          # casi nada sube
    assert r.paso_llegada[25, 30] > r.paso_llegada[10, 30] > 0


def test_cuenco_se_queda_en_el_fondo():
    dem = 0.05 * ((FILAS - 30) ** 2 + (COLS - 30) ** 2)
    r = simular(dem, (10, 30), 2e4, Parametros(max_pasos=20_000))
    assert r.convergio
    assert r.volumen_perdido == 0
    # El centro de masa termina cerca del fondo.
    w = r.h_final / r.h_final.sum()
    assert abs((w * FILAS).sum() - 30) < 1.5
    assert abs((w * COLS).sum() - 30) < 1.5


def test_v1_se_esparce_en_plano_horizontal():
    dem = np.zeros((N, N))
    r = simular(dem, (30, 30), 1e5, Parametros(max_pasos=5_000))
    assert r.h_final.max() < 1.0  # la columna inicial (111 m) se aplanó
    assert r.alcanzado.sum() > 50


def test_canal_en_v_sigue_el_canal():
    dem = -FILAS * 2.0 + np.abs(COLS - 30) * 5.0  # valle en la columna 30
    r = simular(dem, (5, 30), 5e4, Parametros(max_pasos=400))
    cols = np.nonzero(r.alcanzado)[1]
    assert np.abs(cols - 30).max() <= 3   # no se sale del canal
    assert np.nonzero(r.alcanzado)[0].max() > 40


def test_borde_absorbe_el_lodo():
    dem = -FILAS * 3.0
    r = simular(dem, (50, 30), 5e4, Parametros(max_pasos=5_000))
    assert r.volumen_perdido > 0.5 * 5e4
    assert masa(r) == pytest.approx(5e4, rel=1e-9)


def test_mas_volumen_llega_mas_lejos():
    dem = -FILAS * 2.0 + np.abs(COLS - 30) * 5.0 + 0.02 * (FILAS - 40).clip(0) ** 2 * 10
    alcances = []
    for v in (1e4, 1e5, 1e6):
        r = simular(dem, (5, 30), v, Parametros(max_pasos=2_000))
        alcances.append(r.alcanzado.sum())
    assert alcances[0] <= alcances[1] <= alcances[2]


def test_v2_se_detiene_en_plano_horizontal():
    dem = np.zeros((N, N))
    v1 = simular(dem, (30, 30), 1e5, Parametros(max_pasos=5_000))
    v2 = simular(dem, (30, 30), 1e5, Parametros(h_min=2.0, max_pasos=5_000), version="v2")
    assert v2.convergio
    assert v2.h_final.max() >= 2.0             # queda una pila de al menos h_min
    assert v2.alcanzado.sum() < v1.alcanzado.sum()


@pytest.mark.parametrize("params", [Parametros(h_min=1.0, max_pasos=500),
                                    Parametros(tau_y=500.0, max_pasos=500)])
def test_v2_conserva_la_masa(params):
    rng = np.random.default_rng(1)
    dem = rng.uniform(0, 50, (N, N))
    r = simular(dem, (30, 30), 1e5, params, version="v2")
    assert masa(r) == pytest.approx(1e5, rel=1e-9)


def test_v2_mas_h_min_menos_alcance():
    dem = -FILAS * 2.0 + np.abs(COLS - 30) * 5.0
    areas = [simular(dem, (5, 30), 5e4, Parametros(h_min=hm, max_pasos=3_000),
                     version="v2").alcanzado.sum() for hm in (0.0, 1.0, 3.0)]
    assert areas[0] >= areas[1] >= areas[2]
    assert areas[0] > areas[2]


def test_bingham_fluye_en_pendiente_y_para_en_plano():
    # Rampa que se vuelve plana a partir de la fila 30.
    dem = -np.minimum(FILAS, 30) * 15.0 + np.abs(COLS - 30) * 5.0
    r = simular(dem, (2, 30), 5e4, Parametros(tau_y=2000.0, max_pasos=5_000), version="v2")
    filas = np.nonzero(r.alcanzado)[0]
    assert filas.max() >= 30          # bajó toda la rampa
    assert filas.max() < N - 1        # pero se detuvo en lo plano
    assert r.volumen_perdido == 0
