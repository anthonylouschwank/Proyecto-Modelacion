"""Acceso a Sentinel-2 L2A (Collection 1) por el catálogo STAC público de AWS.

Earth Search (Element84) sirve las mismas imágenes L2A de Copernicus como
Cloud-Optimized GeoTIFFs: se puede leer solo el recorte de la AOI sin bajar
tiles completos y sin crear cuenta.

La AOI cae en el borde de 4 tiles MGRS (15PXR, 15PYR, 15PXS, 15PYS), así que
cada fecha se arma uniendo los tiles de ese día.
"""

import os
from collections import defaultdict

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.merge import merge
from rasterio.warp import transform_bounds

from src.config import AOI, CRS

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLECCION = "sentinel-2-c1-l2a"

# Clases de la Scene Classification Layer (SCL) de Sentinel-2 L2A.
SCL_NODATA = 0
SCL_NUBES = (3, 8, 9, 10)  # sombra de nube, nube media, nube alta, cirros
SCL_DESPEJADO = (4, 5, 6, 7, 11)  # vegetación, suelo, agua, sin clasificar, nieve

# Lectura rápida de COGs remotos.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")


def buscar_por_fecha(inicio, fin, max_nubes_tile=60, aoi=AOI):
    """Busca escenas que tocan la AOI y las agrupa por fecha: {fecha: [items]}.

    `max_nubes_tile` filtra por la nubosidad de TODO el tile (110×110 km),
    que puede ser muy distinta a la de nuestra zona; por eso es permisivo.
    """
    bbox_ll = transform_bounds(CRS, "EPSG:4326", *aoi)
    busqueda = Client.open(STAC_URL).search(
        collections=[COLECCION],
        bbox=bbox_ll,
        datetime=f"{inicio}/{fin}",
        query={"eo:cloud_cover": {"lt": max_nubes_tile}},
    )
    por_fecha = defaultdict(list)
    for item in busqueda.items():
        por_fecha[item.datetime.date()].append(item)
    return dict(sorted(por_fecha.items()))


def mosaico(items, asset, res, aoi=AOI, resampling="nearest"):
    """Une un asset (ej. "red", "scl") de varios tiles, recortado a la AOI.

    Devuelve (arreglo 2D, transform). Los píxeles sin dato quedan en 0.
    """
    from rasterio.enums import Resampling

    fuentes = [rasterio.open(it.assets[asset].href) for it in items]
    try:
        for f in fuentes:
            if f.crs.to_string() != CRS:
                raise ValueError(f"Tile en {f.crs}, se esperaba {CRS}")
        arr, transf = merge(
            fuentes, bounds=aoi, res=res, nodata=0,
            resampling=getattr(Resampling, resampling),
        )
    finally:
        for f in fuentes:
            f.close()
    return arr[0], transf


def escala_offset(item, asset):
    """Escala y offset para pasar de número digital a reflectancia."""
    banda = item.assets[asset].extra_fields["raster:bands"][0]
    return banda.get("scale", 1.0), banda.get("offset", 0.0)


def estadisticas_scl(scl):
    """Porcentajes de cobertura, nubes y despejado sobre la AOI."""
    total = scl.size
    validos = scl != SCL_NODATA
    n_validos = validos.sum()
    if n_validos == 0:
        return {"cobertura_pct": 0.0, "nubes_pct": np.nan, "despejado_pct": 0.0}
    return {
        "cobertura_pct": 100 * n_validos / total,
        "nubes_pct": 100 * np.isin(scl, SCL_NUBES).sum() / n_validos,
        "despejado_pct": 100 * np.isin(scl, SCL_DESPEJADO).sum() / total,
    }
