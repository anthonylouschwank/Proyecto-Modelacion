"""Busca fechas de Sentinel-2 con poca nube SOBRE LA ZONA DE ESTUDIO.

La nubosidad que reporta el catálogo es la de todo el tile (110×110 km).
Este script lee la máscara de nubes (SCL) recortada a la AOI, a baja
resolución para que sea rápido, y calcula el % despejado real de la zona.

Uso:
    python -m src.sentinel.buscar --inicio 2019-01-01 --fin 2019-12-31
    python -m src.sentinel.buscar --inicio 2019-01-01 --fin 2019-12-31 \\
        --bbox 726000,1585000,736000,1601000   # solo una barranca (UTM 15N)

Salida: data/raw/sentinel2/candidatas_<inicio>_<fin>.csv, ordenada por % despejado.
"""

import argparse

import pandas as pd

from src.config import AOI, RAW
from src.sentinel.stac import buscar_por_fecha, estadisticas_scl, mosaico

RES_REVISION = 100  # m; suficiente para estimar % de nubes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inicio", required=True, help="AAAA-MM-DD")
    parser.add_argument("--fin", required=True, help="AAAA-MM-DD")
    parser.add_argument("--max-nubes-tile", type=float, default=60,
                        help="filtro previo por nubosidad del tile completo (%%)")
    parser.add_argument("--bbox", help="xmin,ymin,xmax,ymax en UTM 15N (por defecto, la AOI)")
    args = parser.parse_args()

    aoi = tuple(float(v) for v in args.bbox.split(",")) if args.bbox else AOI
    por_fecha = buscar_por_fecha(args.inicio, args.fin, args.max_nubes_tile, aoi)
    print(f"{len(por_fecha)} fechas con escenas; revisando nubes en la zona…")

    filas = []
    for fecha, items in por_fecha.items():
        scl, _ = mosaico(items, "scl", RES_REVISION, aoi)
        est = estadisticas_scl(scl)
        filas.append({
            "fecha": fecha,
            "tiles": " ".join(sorted(it.properties["grid:code"].removeprefix("MGRS-") for it in items)),
            "nubes_tile_pct": round(max(it.properties["eo:cloud_cover"] for it in items), 1),
            **{k: round(v, 1) for k, v in est.items()},
        })
        print(f"  {fecha}  despejado {est['despejado_pct']:5.1f} %  "
              f"(cobertura {est['cobertura_pct']:5.1f} %, nubes {est['nubes_pct']:5.1f} %)")

    tabla = pd.DataFrame(filas).sort_values("despejado_pct", ascending=False)
    salida = RAW / "sentinel2" / f"candidatas_{args.inicio}_{args.fin}.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salida, index=False)
    print(f"\nMejores fechas:\n{tabla.head(10).to_string(index=False)}")
    print(f"\nGuardado {salida}")


if __name__ == "__main__":
    main()
