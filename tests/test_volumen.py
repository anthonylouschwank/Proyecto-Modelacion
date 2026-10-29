"""Pruebas de lluvia → tormentas → volumen y del stub del Monte Carlo."""

import numpy as np
import pandas as pd
import pytest

from src.inputs.volumen import tormentas, volumen_lahar
from src.montecarlo.correr import simular_stub


def serie(lluvias, inicio="2019-05-01"):
    return pd.DataFrame({
        "fecha_hora": pd.date_range(inicio, periods=len(lluvias), freq="h"),
        "lluvia_mm": lluvias,
    })


def test_volumen_lahar():
    # 100 mm en 1 km² con C = 0.5 → 5·10⁴ m³ de agua; con Cs = 0.5 → 10⁵ m³ de lahar.
    assert volumen_lahar(100, 1e6, 0.5, 0.5) == pytest.approx(1e5)
    with pytest.raises(ValueError):
        volumen_lahar(100, 1e6, 0.5, 1.0)


def test_tormentas_se_separan_por_horas_secas():
    # 3 h de lluvia, 6 h secas, 2 h de lluvia → dos tormentas.
    s = serie([10, 10, 10] + [0] * 6 + [15, 15])
    t = tormentas(s, horas_secas=6, umbral_mm=0)
    assert list(t["lluvia_mm"]) == [30, 30]
    assert list(t["max_1h_mm"]) == [10, 15]
    assert (t["periodo"] == "p1").all()


def test_tormentas_se_unen_con_pocas_horas_secas():
    s = serie([10, 10, 10] + [0] * 5 + [15, 15])
    t = tormentas(s, horas_secas=6, umbral_mm=0)
    assert list(t["lluvia_mm"]) == [60]


def test_umbral_y_periodo():
    s = serie([5] + [0] * 10 + [25], inicio="2019-08-01")
    t = tormentas(s, horas_secas=6, umbral_mm=20)
    assert list(t["lluvia_mm"]) == [25]
    assert list(t["periodo"]) == ["p2"]


def test_stub_mas_volumen_mas_area():
    dem = np.zeros((101, 101))
    chico = simular_stub(dem, (50, 50), 1e4).alcanzado
    grande = simular_stub(dem, (50, 50), 1e5).alcanzado
    assert chico[50, 50] and chico.sum() < grande.sum()
    assert not (chico & ~grande).any()
