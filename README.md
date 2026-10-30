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
