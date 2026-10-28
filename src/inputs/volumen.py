"""Lluvia → tormentas → volumen de lahar.

Separa la serie horaria de Open-Meteo en tormentas y convierte la lluvia de
cada una en m³ de lodo con un balance simple:

    V_agua  = P · A · C          (P en m, A = área de la cuenca en m²)
    V_lahar = V_agua / (1 − Cs)

C es el coeficiente de escurrimiento y Cs la concentración de sedimento en
volumen. El área sale de data/processed/lajas_fuente.json (src.inputs.cuenca).

Uso:
    python -m src.inputs.lluvia --inicio 2019-03-26 --fin 2019-12-11   # antes
    python -m src.inputs.volumen
    python -m src.inputs.volumen --umbral 15 --horas-secas 6

Salida: results/montecarlo/tormentas_2019.csv
"""

import argparse
import json

import pandas as pd

from src.config import PROCESSED, RAIZ, RAW

LLUVIA_2019 = RAW / "lluvia" / "lluvia_crater_ecmwf_ifs_2019-03-26_2019-12-11.csv"
SALIDA = RAIZ / "results" / "montecarlo" / "tormentas_2019.csv"

# Periodos entre imágenes Sentinel-2 (ver docs/tareas/00_general.md, sección 2).
PERIODOS = {
    "p1": (pd.Timestamp("2019-03-26"), pd.Timestamp("2019-07-04")),  # calibración
    "p2": (pd.Timestamp("2019-07-04"), pd.Timestamp("2019-12-11")),  # prueba
}
# Una hora cuenta como lluviosa desde 0.1 mm: el modelo da llovizna de 0.0x mm
# casi todas las horas y, sin este mínimo, toda la temporada sería una tormenta.
LLUVIA_MIN_MM = 0.1

# Valores centrales de los rangos del Monte Carlo (src/montecarlo/correr.py),
# solo para la columna de referencia de tormentas_2019.csv.
C_CENTRAL = 0.5
CS_CENTRAL = 0.45


def cargar_lluvia(ruta=LLUVIA_2019):
    return pd.read_csv(ruta, parse_dates=["fecha_hora"])


def periodo_de(fecha):
    for nombre, (ini, fin) in PERIODOS.items():
        if ini <= fecha < fin:
            return nombre
    return None


def tormentas(serie: pd.DataFrame, horas_secas: int = 6, umbral_mm: float = 20) -> pd.DataFrame:
    """Agrupa horas lluviosas en tormentas separadas por >= horas_secas sin lluvia.
    Devuelve las tormentas con lluvia total >= umbral_mm:
    columnas inicio, fin, lluvia_mm, max_1h_mm, periodo ("p1" o "p2")."""
    s = serie.sort_values("fecha_hora").reset_index(drop=True)
    lluvias = s[s["lluvia_mm"] >= LLUVIA_MIN_MM]
    # Nueva tormenta cuando, desde la hora lluviosa anterior, pasaron >= horas_secas horas secas.
    hueco = lluvias["fecha_hora"].diff() > pd.Timedelta(hours=horas_secas)
    t = lluvias.assign(grupo=hueco.cumsum()).groupby("grupo").agg(
        inicio=("fecha_hora", "min"),
        fin=("fecha_hora", "max"),
        lluvia_mm=("lluvia_mm", "sum"),
        max_1h_mm=("lluvia_mm", "max"),
    )
    t["periodo"] = t["inicio"].map(periodo_de)
    t = t[t["lluvia_mm"] >= umbral_mm].reset_index(drop=True)
    t["lluvia_mm"] = t["lluvia_mm"].round(1)
    return t


def volumen_lahar(lluvia_mm: float, area_m2: float, C: float, Cs: float) -> float:
    """V_agua = P · A · C ;  V_lahar = V_agua / (1 − Cs)   (m³)"""
    if not 0 <= Cs < 1:
        raise ValueError("Cs debe estar en [0, 1)")
    return lluvia_mm / 1000 * area_m2 * C / (1 - Cs)


def cargar_fuente():
    ruta = PROCESSED / "lajas_fuente.json"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}: corran antes `python -m src.inputs.cuenca`")
    return json.loads(ruta.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lluvia", default=LLUVIA_2019, help="CSV de src.inputs.lluvia")
    parser.add_argument("--horas-secas", type=int, default=6)
    parser.add_argument("--umbral", type=float, default=20, help="mm por tormenta")
    args = parser.parse_args()

    area = cargar_fuente()["area_cuenca_m2"]
    t = tormentas(cargar_lluvia(args.lluvia), args.horas_secas, args.umbral)
    t["volumen_central_m3"] = [
        round(volumen_lahar(p, area, C_CENTRAL, CS_CENTRAL)) for p in t["lluvia_mm"]
    ]
    t = t[t["periodo"].notna()]
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(SALIDA, index=False)

    print(f"Área de la cuenca: {area / 1e6:.3f} km²; C = {C_CENTRAL}, Cs = {CS_CENTRAL}")
    print(f"Tormentas con >= {args.umbral:g} mm (separadas por >= {args.horas_secas} h secas):")
    for periodo, g in t.groupby("periodo"):
        mayor = g.loc[g["lluvia_mm"].idxmax()]
        print(f"  {periodo}: {len(g)} tormentas; la mayor {mayor['lluvia_mm']:.0f} mm "
              f"el {mayor['inicio']:%Y-%m-%d} → {mayor['volumen_central_m3']:.2e} m³")
    print(f"Guardado {SALIDA}")


if __name__ == "__main__":
    main()
