# Simulación probabilística de lahares en el Volcán de Fuego

Proyecto de Modelación y Simulación: un autómata celular sobre el terreno real
del Volcán de Fuego que, dada una lluvia observada, simula hasta dónde llegaría
un lahar, con Monte Carlo para obtener mapas de probabilidad de alcance.

- Plan del proyecto: [`docs/plan_proyecto_lahares.md`](docs/plan_proyecto_lahares.md)
- Fuentes de datos y cómo descargarlas: [`data/README.md`](data/README.md)
- División del trabajo (4 partes): [`docs/tareas/`](docs/tareas/00_general.md)

## Instalación

```bash
uv venv .venv -p 3.12
uv pip install -p .venv -r requirements.txt
source .venv/bin/activate
```

(o con `python -m venv .venv && pip install -r requirements.txt`)

## Descargar los datos

```bash
python -m src.inputs.dem --preview
python -m src.inputs.lluvia --inicio 2019-05-01 --fin 2019-11-30
python -m src.sentinel.buscar --inicio 2019-01-01 --fin 2020-02-29
python -m src.sentinel.descargar --fecha 2019-03-26
python -m src.validacion.mapas_insivumeh
```

> **Windows con acentos en la ruta** (p. ej. `Modelación`): GDAL se cae sin mensaje
> (código `0xC0000409`) al leer archivos por HTTPS, porque no puede abrir el certificado
> de `certifi` dentro de la carpeta con acentos. Copien `cacert.pem` a una ruta sin
> acentos y apunten ahí antes de descargar:
> `$env:CURL_CA_BUNDLE = "C:\ruta\sin\acentos\cacert.pem"; $env:GDAL_CURL_CA_BUNDLE = $env:CURL_CA_BUNDLE`

## Correr todo el pipeline

En este orden (cada paso usa lo que genera el anterior):

```bash
python -m src.inputs.cuenca                 # fuente, cuenca, cauce y confluencia (P2)
python -m src.inputs.volumen                # tormentas de 2019 y su volumen (P2)
python -m src.sentinel.ndvi                 # mapa observado p1 y p2 (P3)
python -m src.validacion.mapa_amenaza       # mapa del INSIVUMEH clasificado (P4)
python -m src.modelo.calibrar               # calibración de v2 con p1 y v1 vs v2 (P1)
python -m src.montecarlo.correr --n 500 --simulador automata --version v2 --procesos 8
python -m src.validacion.evaluar            # prueba final: p2, puntos clave, INSIVUMEH (P4)
```

Resultados en `results/`: `modelo/registro_iteraciones.md` (proceso iterativo),
`sentinel/umbrales.md`, `montecarlo/` y `validacion/`.

## Pruebas

```bash
python -m pytest
```

## Estructura

```
src/
├── config.py        # zona de estudio, CRS, rutas
├── inputs/          # DEM, lluvia, cuenca de Las Lajas y volumen de lahar
├── modelo/          # autómata celular y demo en Las Lajas
├── montecarlo/      # corridas Monte Carlo y mapa de probabilidad
├── sentinel/        # búsqueda y descarga de Sentinel-2 (validación)
└── validacion/      # mapas del INSIVUMEH y métricas
tests/               # pruebas con pytest
results/             # figuras y tablas (los .tif no se suben)
data/
├── catalogo_lahares.csv   # eventos reales, llenado a mano
├── raw/                   # descargas (no se suben a git)
└── processed/             # generados por los scripts (no se suben a git)
docs/
├── plan_proyecto_lahares.md
└── tareas/                # división del trabajo
```
