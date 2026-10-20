"""Configuración común: zona de estudio, sistema de coordenadas y rutas."""

from pathlib import Path

# Sistema de coordenadas de trabajo: UTM zona 15N (metros).
# Es el mismo de las imágenes Sentinel-2 y del mapa de amenaza del INSIVUMEH,
# así que todo queda alineado sin reproyectar dos veces.
CRS = "EPSG:32615"

# Zona de estudio (AOI) en UTM 15N, en metros: (xmin, ymin, xmax, ymax).
# Cubre el Volcán de Fuego y sus barrancas hacia el sur (Las Lajas, Ceniza,
# Seca, Santa Teresa, etc.) hasta ~30 km del cráter. Incluye toda la
# extensión del mapa de amenaza de lahares del INSIVUMEH (2018).
# Los límites son múltiplos de 30 m para que la cuadrícula del DEM sea exacta.
AOI = (706_800, 1_569_600, 745_200, 1_608_000)

# Cráter del Volcán de Fuego (lon, lat) y en UTM 15N (x, y).
# Punto más alto del DEM en el cono de Fuego (3803 m en el DSM; ~3763 m oficial).
CRATER_LONLAT = (-90.8806, 14.4751)
CRATER_UTM = (728_445, 1_601_325)

# Resolución de la cuadrícula del modelo (m).
RES_DEM = 30
# Resolución de las bandas B04/B08 de Sentinel-2 (m).
RES_S2 = 10

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
