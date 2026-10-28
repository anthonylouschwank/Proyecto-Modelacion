# División del proyecto: reglas generales

Este documento es para **los 4**. Léanlo antes de su parte.

| Parte | Responsable | Archivo | En una frase |
|---|---|---|---|
| **P1 – Modelo** | [nombre] | [01_modelo_automata.md](01_modelo_automata.md) | El autómata celular que mueve el lodo sobre el terreno (v1 → v2 → v3) |
| **P2 – Cuenca, lluvia y Monte Carlo** | [nombre] | [02_cuenca_lluvia_montecarlo.md](02_cuenca_lluvia_montecarlo.md) | De dónde sale el lahar, cuánto lodo produce la lluvia y las miles de corridas |
| **P3 – Sentinel-2** | [nombre] | [03_sentinel2.md](03_sentinel2.md) | El mapa de "dónde pasó el lodo de verdad" a partir de imágenes satelitales |
| **P4 – Validación y documento** | [nombre] | [04_validacion.md](04_validacion.md) | Las métricas que dicen si le atinamos, los puntos de referencia y el documento final |

Contexto completo del proyecto: [`../plan_proyecto_lahares.md`](../plan_proyecto_lahares.md).
Fuentes de datos y cómo bajarlas: [`../../data/README.md`](../../data/README.md).

---

## 1. Cómo encaja todo

```
 P2: cuenca de Las Lajas ──► fuente (celda donde nace el lahar) + área de la cuenca
 P2: lluvia ──► volumen de lodo (m³) ───────────────┐
                                                     ▼
                                 P1: simular(dem, fuente, volumen, parámetros)
                                                     │  (una corrida)
                                                     ▼
                                 P2: Monte Carlo (N corridas) ──► mapa de probabilidad
                                                     │
 P3: Sentinel-2 ──► máscara "observado" ────────────►├──► P4: métricas (Jaccard, alcance,
 P4: mapa INSIVUMEH + puntos clave ─────────────────►┘          puntos clave) ──► documento
```

## 2. Evento de estudio

**Barranca Las Lajas, temporada de lluvias 2019**, partida en dos periodos con las
tres imágenes Sentinel-2 casi sin nubes que ya encontramos:

| Periodo | Imágenes | Uso |
|---|---|---|
| **p1** | 2019-03-26 → 2019-07-04 | **Calibración**: ajustar los parámetros del modelo |
| **p2** | 2019-07-04 → 2019-12-11 | **Prueba**: el modelo NO se ajusta con esto |

Pruebas adicionales: el mapa de amenaza del INSIVUMEH (escenario B) y los eventos del
catálogo (`data/catalogo_lahares.csv`).

## 3. Contratos (lo más importante)

Para no esperarse entre sí, **todos respetan estas reglas**. Si alguien necesita
cambiar un contrato, avisa en el grupo antes.

### 3.1 Una sola cuadrícula

Todo raster que se use en el modelo o en la validación debe estar **exactamente en la
cuadrícula del DEM**:

- Archivo de referencia: `data/raw/dem/dem_fuego_30m.tif`
- **1280 × 1280** celdas de **30 m**, UTM 15N (`EPSG:32615`)
- Esquina superior izquierda: x = 706 800, y = 1 608 000

Así, `mascara_simulada & mascara_observada` funciona directo con NumPy, sin reproyectar.

Para alinear cualquier raster a esa cuadrícula:

```python
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

with rasterio.open("data/raw/dem/dem_fuego_30m.tif") as ref:
    perfil = ref.profile
destino = np.zeros((perfil["height"], perfil["width"]), dtype="float32")
with rasterio.open("mi_raster.tif") as src:
    reproject(
        source=src.read(1), destination=destino,
        src_transform=src.transform, src_crs=src.crs,
        dst_transform=perfil["transform"], dst_crs=perfil["crs"],
        resampling=Resampling.average,  # o nearest para clases
    )
```

### 3.2 Unidades

| Cantidad | Unidad |
|---|---|
| Elevación, espesor de lodo `h` | metros |
| Volumen | m³ |
| Lluvia | mm |
| Área de celda | 900 m² (30 × 30) |
| Probabilidad | 0 a 1 |

### 3.3 Índices de celda

Las celdas se indican como `(fila, col)` de NumPy (fila 0 = norte). Para pasar de
coordenadas UTM a celda: `rasterio.open(dem).index(x, y)`.

### 3.4 Archivos que se pasan entre partes

`data/processed/` **no se sube a git**. Cada archivo procesado lo genera un script,
y quien lo necesite **corre ese script**. Así nadie trabaja con una versión vieja.

| Archivo | Lo genera | Comando | Lo usa |
|---|---|---|---|
| `data/processed/lajas_cuenca.tif` | P2 | `python -m src.inputs.cuenca` | P2, P3, P4 |
| `data/processed/lajas_cauce.tif` | P2 | `python -m src.inputs.cuenca` | P1, P3, P4 |
| `data/processed/lajas_cauce_distancia.tif` | P2 | `python -m src.inputs.cuenca` | P4 |
| `data/processed/lajas_fuente.json` | P2 | `python -m src.inputs.cuenca` | P1, P2 |
| `data/processed/observado_lajas_2019_p1.tif` | P3 | `python -m src.sentinel.ndvi` | P4 |
| `data/processed/observado_lajas_2019_p2.tif` | P3 | `python -m src.sentinel.ndvi` | P4 |
| `data/processed/amenaza_insivumeh_B.tif` | P4 | `python -m src.validacion.mapa_amenaza` | P4 |
| `data/puntos_clave.csv` | P4 | a mano (sí va a git) | P4 |

Las funciones de Python que se comparten (`simular`, `volumen_lahar`, `jaccard`…)
están definidas en el archivo de cada parte.

### 3.5 Mientras el otro no termina: stubs

Si dependen de algo que aún no existe, **no esperen**: hagan una versión falsa con la
misma firma. Ejemplos:
- P2 necesita `simular()` de P1 para el Monte Carlo → usa una función que pinta un
  círculo de radio proporcional al volumen.
- P4 necesita la máscara observada de P3 → prueba las métricas con dos círculos.
- P1 necesita la fuente de P2 → usa la celda más alta del cauce a mano.

## 4. Git

- Cada quien trabaja en **su carpeta** (ver su archivo) para no pisarse.
- `src/config.py` y `requirements.txt` son compartidos: si los cambian, avisen.
- Si agregan una librería, agréguenla a `requirements.txt`.
- Ramas sugeridas: `p1-modelo`, `p2-cuenca-mc`, `p3-sentinel`, `p4-validacion`;
  se integra a `main` en cada hito.
- Instalación: `uv venv .venv -p 3.12 && uv pip install -p .venv -r requirements.txt`

## 5. Cronograma

Asumiendo **entrega el martes 3 de noviembre** (ajusten si es otra fecha).

| Día | Qué pasa |
|---|---|
| **Jue 29 – Vie 30 oct** | Cada quien arranca su parte, con stubs donde haga falta |
| **Vie 30 oct, noche – 🔗 Hito 1** | P2 entrega cuenca, cauce y fuente · P1 tiene v1 corriendo en Las Lajas · P3 tiene la máscara p1 preliminar · P4 tiene métricas y puntos clave |
| **Sáb 31 oct** | P1: v2 · P2: Monte Carlo con el `simular` real · P3: máscara p2 · P4: mapa INSIVUMEH clasificado |
| **Dom 1 nov – 🔗 Hito 2** | **Calibración** con p1 (P1 + P4) · corridas Monte Carlo v3 (P2) |
| **Lun 2 nov** | **Prueba** con p2, mapa INSIVUMEH y catálogo · figuras · cada quien escribe su sección |
| **Mar 3 nov** | P4 integra el documento, todos revisan, entrega |

## 6. Documento final: quién escribe qué

| Sección | Responsable |
|---|---|
| Introducción, problema, qué es un lahar | P4 |
| Datos (DEM, lluvia, Sentinel-2, INSIVUMEH) | P2 (DEM, lluvia) + P3 (Sentinel-2) + P4 (INSIVUMEH) |
| Modelo y **proceso iterativo v1 → v2 → v3** | P1 |
| Lluvia → volumen y Monte Carlo | P2 |
| Validación: método y métricas | P4 |
| Resultados y discusión | P1 + P4 |
| Limitaciones | Todos (cada quien las de su parte) |
| Conclusiones | P4 |

## 7. Si nos atrasamos (se recorta en este orden)

1. LAHARZ propio (usamos el mapa del INSIVUMEH como referencia).
2. Tiempo de llegada (extra de P1).
3. Monte Carlo de 500 → 200 corridas.
4. Validación con p2 por Sentinel-2 → solo mapa INSIVUMEH y catálogo.
