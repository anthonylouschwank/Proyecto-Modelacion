# Datos del proyecto

Todo lo que está en `data/raw/` se **descarga con scripts** y no se sube a git
(ver `.gitignore`). Para regenerarlo:

```bash
python -m src.inputs.dem --preview
python -m src.inputs.lluvia --inicio 2019-05-01 --fin 2019-11-30
python -m src.sentinel.buscar --inicio 2019-01-01 --fin 2020-02-29
python -m src.sentinel.descargar --fecha 2019-03-26
python -m src.validacion.mapas_insivumeh
```

Ninguna fuente necesita cuenta ni API key.

## Zona de estudio

Definida en `src/config.py`:

- **Sistema de coordenadas:** UTM 15N (`EPSG:32615`), en metros. Es el mismo de
  Sentinel-2 y de los mapas del INSIVUMEH.
- **AOI:** x 706 800–745 200, y 1 569 600–1 608 000 (38.4 × 38.4 km).
  Incluye Fuego, Acatenango (norte), Agua (este), las barrancas del sur y
  Escuintla.
- **Cráter de Fuego:** (728 445, 1 601 325), punto más alto del cono en el DEM.

---

## 1. Terreno – Copernicus DEM GLO-30

| | |
|---|---|
| Script | `src/inputs/dem.py` |
| Fuente | Bucket público de AWS `copernicus-dem-30m` (tiles N14 W091 y N14 W092) |
| Salida | `data/raw/dem/dem_fuego_30m.tif`: 1280 × 1280 celdas de 30 m, float32 |
| Rango | 77 m – 3968 m (el máximo es Acatenango; Fuego da 3803 m) |

**Limitación:** es un modelo de **superficie** (DSM), no de terreno: incluye
árboles y edificios. Por eso Fuego sale ~40 m más alto que su altura oficial
(3763 m). Además es de 2011–2015: no refleja el relleno de las barrancas de 2018.

## 2. Lluvia – Open-Meteo

| | |
|---|---|
| Script | `src/inputs/lluvia.py` |
| Fuente | Open-Meteo Historical Weather API (`archive-api.open-meteo.com`) |
| Modelo | **`ecmwf_ifs` (~9 km, desde 2017)** por defecto |
| Salida | `data/raw/lluvia/lluvia_<punto>_<modelo>_<inicio>_<fin>.csv` (horaria, hora local) |

**Elección del modelo:** comparamos los dos en el cráter para jun–oct 2019:

| Modelo | Resolución | Lluvia jun–oct 2019 | Máx. diaria |
|---|---|---|---|
| `ecmwf_ifs` (= "best_match" desde 2017) | ~9 km | **1699 mm** | 87 mm |
| `era5` | ~25 km | 1143 mm | 58 mm |

ERA5 da ~33 % menos y suaviza los picos, justo lo que dispara lahares. Usamos
IFS; ERA5 solo para fechas antes de 2017.

**Limitación:** sigue siendo un modelo meteorológico, no un pluviómetro. La
celda de 9 km promedia todo el cono, así que la lluvia "real" en una barranca
puede ser mayor. Se cubre con el factor de corrección de lluvia en el Monte Carlo.

Temporada 2019 (1 may – 30 nov) en el cráter: 3253 mm en total, máximo diario
140 mm (13 sep), máximo en 3 horas 85 mm.

## 3. Imágenes – Sentinel-2 L2A (Collection 1)

| | |
|---|---|
| Scripts | `src/sentinel/buscar.py`, `src/sentinel/descargar.py` |
| Fuente | Catálogo STAC **Earth Search** de AWS (`earth-search.aws.element84.com/v1`), colección `sentinel-2-c1-l2a` |
| Salida | `s2_<fecha>_refl.tif` (B04 rojo, B08 NIR en reflectancia), `s2_<fecha>_scl.tif` (máscara), `s2_<fecha>_rgb.png` (vista previa) |

**¿Por qué no el Copernicus Browser?** Earth Search tiene las mismas imágenes
L2A como Cloud-Optimized GeoTIFF: los scripts leen **solo el recorte** de la
AOI, sin bajar tiles completos ni crear cuenta. Una fecha completa tarda ~30 s.

**Detalles técnicos:**
- La AOI cae en el borde de **4 tiles** (15PXR, 15PYR, 15PXS, 15PYS); los
  scripts los unen por fecha.
- Las bandas vienen como enteros: `reflectancia = DN × 0.0001 − 0.1`. El
  script ya lo aplica, leyendo la escala y el offset de los metadatos.
- `buscar.py` calcula el % de nubes **sobre la AOI** con la máscara SCL. La
  nubosidad del catálogo es la de todo el tile (110 × 110 km) y engaña: el
  2019-03-26 el catálogo dice 40 % de nubes y en la AOI hay menos de 1 %.

**Fechas candidatas para la temporada 2019** (ver `candidatas_*.csv`):

| Uso | Fecha | % despejado en la AOI |
|---|---|---|
| Antes de la temporada | **2019-03-26** | 97.7 |
| A media temporada | **2019-07-04** | 98.2 |
| Después de la temporada | **2019-12-11** / **2020-01-10** | 96.6 / 98.2 |

Con la de julio se puede partir la temporada en dos periodos.

## 4. Mapas de amenaza de lahares – INSIVUMEH

| | |
|---|---|
| Script | `src/validacion/mapas_insivumeh.py` |
| Fuente | insivumeh.gob.gt → Mapas de amenaza volcánica |
| Salida | `data/raw/insivumeh/fuego_lahares_escenario_*.tif` |

"Mapa preliminar de amenaza de lahares – crisis eruptiva de junio 2018",
escenarios **A (lluvias moderadas)** y **B (lluvias muy intensas)**.
Georreferenciado en UTM 15N a ~5.5 m/píxel.

**Lo que muestra el escenario B:**
- Zonas de amenaza **alta (rojo), media (naranja) y baja (amarillo)** por
  barranca, más el depósito del flujo piroclástico del 3 de junio de 2018.
- Comunidades y carreteras como puntos de referencia: El Rodeo, La Reina,
  La Trinidad, Siquinalá, Santa Lucía Cotzumalguapa, Escuintla, RN-14 y CA-2.
  Sirven como **puntos clave** para la métrica de acierto sí/no.
- Los bordes "en sierra" de las zonas son típicos de **LAHARZ** con varios
  volúmenes anidados. Si se confirma, este mapa ES el benchmark de LAHARZ ya
  hecho por el INSIVUMEH.

**Ojo:** es la **imagen RGB del mapa**, no zonas clasificadas. Para comparar
numéricamente hay que extraer las zonas por color. Del escenario A, el TIF y el PDF
daban 404; solo está el JPG (sin georreferencia).

## 5. Catálogo de eventos – `data/catalogo_lahares.csv`

Se llena **a mano** (tarea de validación). Columnas: fecha, hora, barranca,
intensidad (débil / moderado / fuerte), ríos alcanzados, alcance descrito,
fuente, referencia, url, notas.

**Fuentes:**
- **INSIVUMEH:** la web solo muestra el boletín de lahar *activo*, no tiene
  archivo histórico. Los boletines pasados están en su cuenta de X (@insivumehgt).
- **Smithsonian Global Volcanism Program** (volcano.si.edu, Fuego = 342090):
  los reportes semanales resumen los boletines del INSIVUMEH con fecha y barranca.
  Es la mejor fuente archivada, pero el sitio estaba caído el 2026-10-27.
  Reintentar.
- **CONRED** (conred.gob.gt): boletines informativos.
- **Papers** (ver `docs/plan_proyecto_lahares.md`, sección 12).

---

## Pendientes

- [ ] Delimitar la cuenca de Las Lajas con el DEM (área para lluvia → volumen).
- [ ] Bajar las fechas 2019-07-04 y 2019-12-11 (o 2020-01-10) y calcular ΔNDVI.
- [ ] Llenar el catálogo de eventos de 2019 (GVP + X del INSIVUMEH).
- [ ] Extraer las zonas del mapa de amenaza escenario B por color.
- [ ] Revisar si los autores del paper del dron (2021) comparten sus DEMs.
