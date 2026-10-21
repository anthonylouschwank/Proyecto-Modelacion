"""Descarga lluvia horaria histórica de Open-Meteo (sin cuenta ni API key).

Modelo por defecto: ECMWF IFS (~9 km, desde 2017). Es lo mismo que usa
"best_match" de Open-Meteo para esas fechas. ERA5 (~25 km) llega hasta 1940,
pero en Fuego da ~33 % menos lluvia en la temporada 2019 porque suaviza las
tormentas. Úsenlo solo para fechas anteriores a 2017.

Uso:
    python -m src.inputs.lluvia --inicio 2019-05-01 --fin 2019-11-30
    python -m src.inputs.lluvia --inicio 2019-05-01 --fin 2019-11-30 --modelo era5
    python -m src.inputs.lluvia --inicio 2024-10-10 --fin 2024-10-16 \\
        --punto ceniza_alta,14.46,-90.90

Salida: data/raw/lluvia/lluvia_<punto>_<modelo>_<inicio>_<fin>.csv
        columnas: fecha_hora (hora local de Guatemala), lluvia_mm
"""

import argparse
import time
from datetime import date

import pandas as pd
import requests

from src.config import CRATER_LONLAT, RAW

URL = "https://archive-api.open-meteo.com/v1/archive"
MODELOS = {
    "ecmwf_ifs": date(2017, 1, 1),  # ~9 km
    "era5": date(1940, 1, 1),       # ~25 km
}
SALIDA_DIR = RAW / "lluvia"


def descargar_lluvia(lat, lon, inicio, fin, modelo="ecmwf_ifs", reintentos=3):
    """Lluvia horaria (mm) en un punto. La API es lenta: ~30 s por consulta."""
    if inicio < MODELOS[modelo]:
        raise ValueError(f"{modelo} solo tiene datos desde {MODELOS[modelo]}; use --modelo era5")

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": inicio.isoformat(),
        "end_date": fin.isoformat(),
        "hourly": "precipitation",
        "models": modelo,
        "timezone": "America/Guatemala",
    }
    for intento in range(1, reintentos + 1):
        try:
            r = requests.get(URL, params=params, timeout=300)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            if intento == reintentos:
                raise
            print(f"  intento {intento} falló ({e}); reintentando…")
            time.sleep(10 * intento)

    datos = r.json()
    # Open-Meteo devuelve la celda de su cuadrícula más cercana al punto pedido.
    print(f"  celda usada por Open-Meteo: lat {datos['latitude']:.3f}, lon {datos['longitude']:.3f}")
    # La columna se llama "precipitation" o "precipitation_<modelo>" según la versión de la API.
    clave = next(k for k in datos["hourly"] if k.startswith("precipitation"))
    return pd.DataFrame({
        "fecha_hora": pd.to_datetime(datos["hourly"]["time"]),
        "lluvia_mm": datos["hourly"][clave],
    })


def resumen(serie):
    diaria = serie.set_index("fecha_hora")["lluvia_mm"].resample("D").sum()
    max_3h = serie["lluvia_mm"].rolling(3).sum().max()
    print(f"  total: {serie['lluvia_mm'].sum():.0f} mm en {len(diaria)} días")
    print(f"  máx. diaria: {diaria.max():.1f} mm ({diaria.idxmax().date()})")
    print(f"  máx. en 3 horas: {max_3h:.1f} mm")
    print(f"  horas sin dato: {serie['lluvia_mm'].isna().sum()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inicio", required=True, type=date.fromisoformat, help="AAAA-MM-DD")
    parser.add_argument("--fin", required=True, type=date.fromisoformat, help="AAAA-MM-DD")
    parser.add_argument("--modelo", default="ecmwf_ifs", choices=MODELOS)
    parser.add_argument(
        "--punto", action="append",
        help="nombre,lat,lon (se puede repetir). Por defecto: el cráter de Fuego.",
    )
    args = parser.parse_args()

    puntos = []
    for p in args.punto or [f"crater,{CRATER_LONLAT[1]},{CRATER_LONLAT[0]}"]:
        nombre, lat, lon = p.split(",")
        puntos.append((nombre, float(lat), float(lon)))

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    for nombre, lat, lon in puntos:
        print(f"[{nombre}] {args.modelo}, {args.inicio} → {args.fin}")
        serie = descargar_lluvia(lat, lon, args.inicio, args.fin, args.modelo)
        resumen(serie)
        salida = SALIDA_DIR / f"lluvia_{nombre}_{args.modelo}_{args.inicio}_{args.fin}.csv"
        serie.to_csv(salida, index=False)
        print(f"  guardado {salida}")


if __name__ == "__main__":
    main()
