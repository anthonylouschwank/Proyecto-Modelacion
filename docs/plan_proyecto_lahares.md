# Simulación probabilística de lahares en el Volcán de Fuego

**Curso:** Modelación y Simulación
**Equipo:** 4 integrantes
**Entrega:** proyecto completo, inicios de noviembre 2026

Documento interno del equipo: qué vamos a hacer, cómo y quién hace qué.

---

## 1. Resumen en una frase

Construir un **autómata celular** sobre el terreno real del Volcán de Fuego que, dada una **lluvia observada**, simule **hasta dónde llegaría un lahar** por una barranca, usando **Monte Carlo** para producir un **mapa de probabilidad de alcance**, y **validarlo contra eventos reales** con varias fuentes independientes.

---

## 2. Contexto: ¿qué es un lahar?

Un **lahar** es un flujo de lodo volcánico: agua de lluvia mezclada con ceniza, arena y rocas sueltas que baja por las barrancas del volcán con una consistencia parecida al concreto fresco.

- **No necesita erupción.** Basta con lluvia fuerte sobre material suelto.
- En el Volcán de Fuego ocurren **casi cada época de lluvia** (barrancas Las Lajas, Ceniza, Seca, Santa Teresa, El Jute, etc.).
- Pueden recorrer **decenas de km** siguiendo los ríos y han dañado varias veces la RN-14 y el puente Las Lajas.

**Ojo, no confundir con un flujo piroclástico.** El flujo piroclástico (lo que sepultó San Miguel Los Lotes el 3 de junio de 2018) es una avalancha de gas caliente y ceniza **durante** la erupción. Nosotros modelamos **lahares**, no flujos piroclásticos.

| | Lahar | Flujo piroclástico |
|---|---|---|
| ¿Qué es? | Lodo (agua + material volcánico) | Gas caliente + ceniza + roca |
| ¿Cuándo? | Cuando llueve | Durante la erupción |
| Velocidad | Decenas de km/h | Más de 100 km/h |
| Disparador | **Lluvia** | Colapso de la columna eruptiva |

---

## 3. Pregunta del proyecto

> **"Si con la lluvia observada en un día dado se genera un lahar en la barranca X, ¿qué zonas alcanza y con qué probabilidad?"**

Ejemplo del tipo de resultado que queremos poder decir:

> *"Con los 40 mm que cayeron en la cuenca de Las Lajas, si se generara un lahar, hay 80 % de probabilidad de que alcance el punto A y 25 % de que alcance el puente de la RN-14."*

### Alcance

**Sí hacemos:**
- Simular el **recorrido y el área cubierta** de un lahar (dado que ocurre).
- Convertir **lluvia → volumen de lodo** con incertidumbre.
- **Mapas de probabilidad** de alcance con Monte Carlo.
- **Validación** contra eventos reales.

**No hacemos:**
- Predecir **si** se va a formar un lahar (eso es otro modelo, estadístico, fuera del enfoque de simulación).
- Flujos piroclásticos.
- Física completa de fluidos (CFD / Navier-Stokes).

---

## 4. Flujo general del sistema

```
 ┌──────────────┐    ┌───────────────────┐    ┌──────────────────────┐
 │ Lluvia       │    │ Lluvia → Volumen  │    │ Autómata celular     │
 │ (Open-Meteo) │──► │ (cuenca, % escu-  │──► │ sobre DEM real       │──┐
 └──────────────┘    │  rrimiento, % de  │    │ (Copernicus GLO-30)  │  │
                     │  sedimento)       │    └──────────────────────┘  │
                     └───────────────────┘                              │
                              ▲                                         ▼
                     ┌───────────────────┐                   ┌─────────────────────┐
                     │ Monte Carlo       │                   │ Mapa de probabilidad│
                     │ (N corridas con   │◄──────────────────│ de alcance          │
                     │  parámetros       │   se repite N     └─────────────────────┘
                     │  aleatorios)      │   veces                    │
                     └───────────────────┘                            ▼
                                                           ┌─────────────────────┐
                                                           │ Validación contra   │
                                                           │ eventos reales      │
                                                           └─────────────────────┘
```

---

## 5. El modelo

### 5.1 Autómata celular

- **Cuadrícula:** el DEM de la barranca, celdas de ~30 × 30 m.
- **Estado de cada celda:**
  - `z` = elevación del terreno (fija)
  - `h` = espesor de lodo en la celda
- **Vecindad:** Moore (8 vecinos).
- **Regla general:** en cada paso, cada celda reparte parte de su lodo hacia las vecinas cuya **superficie total** (`z + h`) está más baja, en proporción a la diferencia de altura.
  - Referencia: algoritmo de **minimización de diferencias** de Di Gregorio & Serra (1999), base de los modelos SCIDDICA para flujos de detritos.
- **Fin de la simulación:** cuando ninguna celda mueve más de un umbral de lodo.

### 5.2 Iteraciones del modelo (el "proceso iterativo" que pide el reglamento)

| Versión | Qué agrega | Qué esperamos ver |
|---|---|---|
| **v1** | El lodo solo sigue la pendiente; no se detiene hasta que todo está plano | Llega demasiado lejos, como agua y no como lodo |
| **v2** | **Espesor mínimo de detención** (el lodo espeso no fluye bajo cierto espesor, según la pendiente) + **fricción / factor de relajación** | Se detiene en zonas planas; el alcance se acerca a la realidad |
| **v3** | **Lluvia → volumen** como entrada + **Monte Carlo** sobre parámetros inciertos | Mapa de probabilidad en vez de una sola mancha |
| *Extra* | Tiempo de llegada a puntos clave | Útil como tiempo de alerta |

**En cada versión documentamos:** qué cambió, por qué, las métricas de error contra la realidad y qué falla motivó la siguiente versión.

### 5.3 Lluvia → volumen de lodo

```
V_agua  = P × A_cuenca × C
V_lahar = V_agua / (1 − Cs)
```

| Símbolo | Significado | Fuente |
|---|---|---|
| `P` | Lluvia acumulada del evento (m) | Open-Meteo |
| `A_cuenca` | Área de la cuenca de la barranca (m²) | Se calcula del DEM |
| `C` | Coeficiente de escurrimiento (fracción de la lluvia que baja) | Rango de la literatura → Monte Carlo |
| `Cs` | Concentración de sedimento en volumen | Literatura: flujos hiperconcentrados ~20–60 %, flujos de detritos >60 % → Monte Carlo |

> Los rangos exactos de `C` y `Cs` se definen con los papers de Fuego (sección 10) y se ajustan en la calibración.

### 5.4 Monte Carlo

- **Parámetros aleatorios:** `C`, `Cs`, espesor mínimo de detención, coeficiente de fricción y un factor de corrección de la lluvia (porque Open-Meteo subestima tormentas cortas).
- **N corridas** (objetivo: 500–1000).
- **Salida:** para cada celda, `P(alcance) = (corridas donde la celda tuvo lodo) / N`.

Tamaño aproximado: Las Lajas es de unos 15 km × 3 km, unas 50,000 celdas a 30 m. Es manejable con NumPy vectorizado; si hace falta, usamos Numba.

---

## 6. Datos

### 6.1 Datos de entrada

| Dato | Fuente | Notas |
|---|---|---|
| Terreno (DEM) | **Copernicus DEM GLO-30** | 30 m, gratis |
| Lluvia | **Open-Meteo Historical Weather API** | Gratis, sin cuenta. Es **reanálisis ERA5 (~25 km)**, no observación directa: suaviza tormentas fuertes y cortas |
| Parámetros físicos | Papers de Fuego y de lahares en general | Rangos para Monte Carlo |

### 6.2 Datos de validación (la "verdad")

| Fuente | Qué valida | Confianza |
|---|---|---|
| **Boletines INSIVUMEH (BEFGO)** | **Cuándo y dónde** hubo lahar, a qué río llegó | Alta para eso: es la autoridad oficial y detecta lahares con estaciones sísmicas. No da áreas ni volúmenes |
| **Sentinel-2 L2A procesado** | **Qué área cubrió** el lodo | Alta si la imagen está limpia |
| **Papers revisados por pares** | **Volúmenes, depósitos y parámetros** | La más alta |
| **LAHARZ** (ecuaciones del USGS) | Punto de comparación contra el método estándar | Referencia oficial |

**Idea clave: triangulación.** Ninguna fuente carga sola la validación; cada una cubre una parte distinta.

### 6.3 Procesamiento de Sentinel-2

- **Producto:** Level-2A del Copernicus Data Space (ya viene con **corrección atmosférica** y **máscara de nubes** en la banda SCL; disponible desde 2015 gracias al reprocesamiento Collection-1).
- **Método:** diferencia de **NDVI** entre una imagen **antes** y una **después**. Donde había vegetación y ya no la hay, pasó el lodo.
  ```
  NDVI = (B8 − B4) / (B8 + B4)
  ΔNDVI = NDVI_antes − NDVI_después  →  umbral  →  máscara de "lodo"
  ```
- **Par de imágenes objetivo:** fin de época seca (abril–mayo) vs. inicio de la siguiente época seca (noviembre–diciembre), cuando hay menos nubes.
- **Evento objetivo:** **Las Lajas, temporada de lluvias 2019** (muchos lahares retrabajando el material de 2018, sin mezclarse con el flujo piroclástico).
- **Limitación:** la imagen muestra la **temporada acumulada**, no un solo lahar. Comparamos contra la unión de los eventos más grandes simulados de esa temporada.
- **Regla de corte:** si para el **23 de octubre** no hay un par limpio → **plan B:** trazar el área a mano en **Google Earth Pro** (imágenes históricas).

### 6.4 Calibración vs. prueba (sin hacer trampa)

| Uso | Evento(s) | Datos |
|---|---|---|
| **Calibración** (ajustar parámetros) | Las Lajas, temporada 2019 | Sentinel-2 + papers |
| **Prueba** (el modelo no los "vio") | Las Lajas 2021 (depósitos medidos con dron, según paper) y 2–3 lahares de 2024–2026 con boletín (ej. Barranca Ceniza → río Achiguate) | Papers + boletines + Open-Meteo de esos días |

---

## 7. Validación: métricas

1. **Índice de Jaccard** entre el área simulada `S` y la real `R`:
   `J = |S ∩ R| / |S ∪ R|` (1 = perfecto, 0 = nada en común)
2. **Error de alcance:** km de diferencia entre el alcance simulado y el real.
3. **Puntos clave (sí/no):** ¿llega al punto A o al puente? → aciertos, falsas alarmas y fallos.
4. **Calibración probabilística:** de los puntos con P ≈ 70 %, ¿se alcanzó cerca del 70 % en la realidad?
5. **Contra LAHARZ:** implementamos sus ecuaciones semi-empíricas (Iverson, Schilling & Vallance, 1998):
   - Área de sección transversal: `A = 0.05 · V^(2/3)`
   - Área planimétrica inundada: `B = 200 · V^(2/3)`

   y comparamos su Jaccard con el nuestro en los mismos eventos.

**Lo que demostraría que el modelo es significativo:** un buen desempeño en los **eventos de prueba**, que no se usaron para calibrar.

---

## 8. Limitaciones (para documentar desde el inicio)

- **Lluvia:** Open-Meteo es reanálisis a ~25 km; subestima tormentas convectivas cortas en montaña.
- **Terreno cambiante:** cada lahar erosiona y rellena la barranca; el DEM es de una fecha fija.
- **Sentinel-2:** nubes en época de lluvia; la imagen muestra la temporada acumulada, no eventos individuales.
- **Boletines:** cualitativos (débil / moderado / fuerte), sin volúmenes.
- **Modelo:** el autómata simplifica la física del flujo (sin erosión ni cambios de reología en v1–v3).
- **Disponibilidad de material:** asumimos que hay sedimento suelto suficiente (razonable en Fuego por su actividad constante).

---

## 9. Organización del equipo

### Roles

| Integrante | Rol | Responsabilidades |
|---|---|---|
| **P1** | Modelo | Autómata celular v1 → v2 → v3, optimización del código |
| **P2** | Datos de entrada | DEM, delimitación de la cuenca, Open-Meteo, lluvia → volumen, motor de Monte Carlo |
| **P3** | Sentinel-2 | Búsqueda de imágenes, procesamiento ΔNDVI, máscara de área real (o plan B) |
| **P4** | Validación | Catálogo de boletines, parámetros de papers, LAHARZ, métricas, mapas y gráficas |

**Documento final:** todos, cada uno escribe su sección.

### Cronograma

| Fechas | P1: Modelo | P2: Datos de entrada | P3: Sentinel-2 | P4: Validación |
|---|---|---|---|---|
| **21–22 oct** | Estructura del repo; CA v1 en una cuadrícula de prueba | Descargar DEM de Las Lajas; recortar la zona; calcular la cuenca | Cuenta en Copernicus Data Space; buscar pares de imágenes 2019 | Catálogo de boletines (fecha, barranca, río); leer papers clave |
| **23–25 oct** | CA v1 sobre el DEM real; empezar v2 | Script de Open-Meteo; fórmula lluvia → volumen | **23 oct: decisión Sentinel o plan B.** Procesar ΔNDVI | Extraer rangos de parámetros de papers; implementar LAHARZ |
| **26–28 oct** | CA v2 completo; métricas v1 vs. v2 | Motor de Monte Carlo; integrarlo con el CA | Limpiar la máscara; exportarla a la misma cuadrícula del DEM | Funciones de métricas (Jaccard, alcance, puntos clave) |
| **29–31 oct** | CA v3 (lluvia + Monte Carlo); calibración con 2019 | Corridas de Monte Carlo para los eventos de prueba | Apoyo con mapas y figuras | **Validación con eventos de prueba**; comparación contra LAHARZ |
| **1–3 nov** | Documento: modelo e iteraciones | Documento: datos y Monte Carlo | Documento: Sentinel-2 | Documento: validación, resultados y limitaciones |

### Qué recortar si nos atrasamos (en este orden)

1. Calibración probabilística (métrica 4).
2. Comparación contra LAHARZ.
3. Reducir Monte Carlo a ~200 corridas.
4. Sentinel-2 → plan B con Google Earth Pro.

---

## 10. Stack técnico

- **Python:** `numpy`, `numba` (si hace falta velocidad), `rasterio`, `geopandas`, `shapely`, `matplotlib`, `requests` (Open-Meteo).
- **QGIS:** visualización de mapas y trazado manual (plan B).
- **Copernicus Browser / Data Space:** descarga de Sentinel-2 L2A y DEM.

### Estructura sugerida del repositorio

```
lahares-fuego/
├── data/
│   ├── raw/          # DEM, imágenes Sentinel-2, CSV de lluvia
│   └── processed/    # recortes, máscaras, cuencas
├── src/
│   ├── ca/           # autómata celular (v1, v2, v3)
│   ├── inputs/       # DEM, Open-Meteo, lluvia → volumen
│   ├── montecarlo/
│   ├── sentinel/     # procesamiento ΔNDVI
│   └── validation/   # métricas, LAHARZ
├── notebooks/        # experimentos por iteración
├── results/          # mapas, figuras, tablas de métricas
└── docs/             # documento final
```

---

## 11. Entregables

1. Código del simulador (CA + Monte Carlo + validación).
2. Mapas de probabilidad de alcance para los eventos estudiados.
3. Tabla de métricas por versión (v1, v2, v3) y contra LAHARZ.
4. Documento con el proceso iterativo, resultados y limitaciones.

---

## 12. Referencias y fuentes

**Papers de Fuego**
- Buondonno, C. *Rain generated lahars prior to the 2018 catastrophic eruption of Fuego.* Michigan Tech. https://digitalcommons.mtu.edu/etdr/1150/
- *UAV-Based Quantification of Dynamic Lahar Channel Morphology at Volcán de Fuego, Guatemala.* Remote Sensing, 2023. https://doi.org/10.3390/rs15153713
- *Determination of Primary and Secondary Lahar Flow Paths of the Fuego Volcano (Guatemala) Using Morphometric Parameters.* Remote Sensing, 2019. https://doi.org/10.3390/rs11060727
- *Dynamics of rain-triggered lahars and destructive power inferred from seismo-acoustic arrays and time-lapse camera correlation at Volcán de Fuego.* Natural Hazards, 2024. https://link.springer.com/article/10.1007/s11069-024-06926-1
- *Tracking secondary lahar flow paths and characterizing pulses and surges using infrasound array networks at Volcán de Fuego.* https://par.nsf.gov/biblio/10438948

**Métodos**
- Iverson, R. M., Schilling, S. P., & Vallance, J. W. (1998). *Objective delineation of lahar-inundation hazard zones.* GSA Bulletin (base de LAHARZ).
- Di Gregorio, S., & Serra, R. (1999). *An empirical method for modelling and simulating some complex macroscopic phenomena by cellular automata.* Future Generation Computer Systems (base de SCIDDICA).

**Datos**
- Copernicus Data Space: Sentinel-2 L2A. https://documentation.dataspace.copernicus.eu/Data/Others/Sentinel2_L2A_baseline.html
- Open-Meteo Historical Weather API. https://open-meteo.com/en/docs/historical-weather-api
- INSIVUMEH, boletines vulcanológicos especiales (BEFGO). https://insivumeh.gob.gt
- CONRED, boletines informativos. https://conred.gob.gt
