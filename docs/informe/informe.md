---
title: "Simulación probabilística de lahares en la barranca Las Lajas, Volcán de Fuego"
subtitle: "Proyecto final – CC2017 Modelación y Simulación, Universidad del Valle de Guatemala"
author: "Leonardo Mejía (23648) · [Nombre] (23559) · [Nombre] (23074) · [Nombre] (23410)"
date: "Noviembre de 2026"
lang: es
---

**Repositorio:** <https://github.com/anthonylouschwank/Proyecto-Modelacion>

# 1. Descripción del problema

Un **lahar** es un flujo de lodo volcánico: agua de lluvia mezclada con ceniza, arena y
bloques que baja por las barrancas de un volcán con una consistencia parecida al concreto
fresco. No necesita una erupción: basta con lluvia fuerte sobre material suelto. En el
Volcán de Fuego hay lahares casi cada época de lluvia, y en la barranca **Las Lajas** han
dañado varias veces el puente de la RN-14 y amenazado a El Rodeo y La Reina.

No hay que confundirlo con el **flujo piroclástico** del 3 de junio de 2018 (gas caliente
y ceniza durante la erupción), que sepultó San Miguel Los Lotes. Ese evento importa aquí
por otra razón: dejó la barranca Las Lajas sin vegetación y llena de material suelto, la
fuente de los lahares de los años siguientes.

**Pregunta del proyecto:** si con la lluvia observada en un periodo se genera un lahar
en Las Lajas, **¿qué zonas alcanza y con qué probabilidad?**

# 2. Análisis

- **Es un problema espacial y con incertidumbre.** El alcance depende del terreno real,
  del volumen de lodo y de la "resistencia" del lodo, y ninguno de los dos últimos se
  conoce con precisión. Una sola simulación daría una falsa certeza: lo útil para gestión
  de riesgo es un **mapa de probabilidad**.
- **Datos disponibles y sus límites.**
  - Terreno: Copernicus DEM GLO-30 (30 m), un modelo de **superficie** (incluye árboles y
    casas) de antes de 2018.
  - Lluvia: Open-Meteo (modelo ECMWF IFS, celda de ~9 km) en el cráter, horaria.
  - "Verdad": imágenes Sentinel-2 L2A (10 m) casi sin nubes del 2019-03-26, 2019-07-04 y
    2019-12-11; boletines de CONRED e INSIVUMEH; mapa de amenaza de lahares del INSIVUMEH
    (2018, escenario B).
- **Calibración y prueba separadas.** La temporada 2019 se parte en dos periodos entre
  las tres imágenes: **p1** (26 mar – 4 jul) para calibrar y **p2** (4 jul – 11 dic)
  para probar sin volver a ajustar.

# 3. Propuesta de solución

Combinar tres técnicas del curso:

1. **Autómata celular** sobre el DEM real que mueve el lodo celda por celda.
2. **Modelo de entrada** que convierte la lluvia de cada tormenta en volumen de lodo.
3. **Simulación Monte Carlo** sobre los parámetros inciertos para obtener la probabilidad
   de alcance de cada celda.

Y **validar** el resultado contra fuentes independientes: Sentinel-2 (con métricas de
traslape), puntos clave con desenlace conocido y el mapa de amenaza oficial.

# 4. Descripción de la solución

El código está en `src/` y se corre en el orden del README ("Correr todo el pipeline").

## 4.1 Cuenca, cauce y volumen (`src/inputs/`)

- `cuenca.py` (pysheds): rellena el DEM, calcula dirección de flujo D8 y acumulación,
  ubica la **fuente** del lahar sobre Las Lajas a 1829 m (celda (287, 812)) y traza el
  **cauce** hasta el borde de la zona con su distancia acumulada. Detecta la
  **confluencia con el río Guacalate** en el km 7.44, donde el área drenada salta de
  11.3 km² a 124 km².
- `volumen.py`: separa la serie horaria en tormentas (≥ 20 mm, separadas por ≥ 6 h secas)
  y calcula el volumen con un balance simple:

  $$V_{agua} = P \cdot A \cdot C, \qquad V_{lahar} = \frac{V_{agua}}{1 - C_s}$$

  con `A` = 11.3 km² (Las Lajas hasta la confluencia), `C` el coeficiente de
  escurrimiento y `Cs` la concentración de sedimento.

![Cuenca, cauce y fuente de Las Lajas sobre el DEM y Sentinel-2.](../../results/montecarlo/cuenca_lajas.png)

## 4.2 Autómata celular (`src/modelo/automata.py`)

Algoritmo de **minimización de diferencias** (Di Gregorio y Serra, 1999), base de los
modelos SCIDDICA de flujos de detritos. Cada celda tiene terreno `z` y espesor de lodo
`h`; con superficie libre $H = z + h$ y vecindad de Moore:

1. Lodo que puede moverse: $h_{mov} = h$ en v1 y $h_{mov} = \max(0,\, h - h_{crit})$ en v2,
   con espesor crítico de Bingham
   $$h_{crit} = \max\!\left(h_{min},\; \frac{\tau_y}{\rho\, g \sin\theta}\right)$$
   donde $\theta$ es la pendiente de la superficie libre hacia el vecino más bajo. En
   pendiente fuerte $h_{crit}$ es pequeño (el lodo fluye); en la planicie es enorme (se detiene).
2. Sale $\text{relajación} \cdot \min(h_{mov}, (H_i - \min_j H_j)/2)$, repartido entre los
   vecinos más bajos en proporción a $(H_i - H_j)/d_{ij}$.
3. El volumen se suelta en la fuente durante 100 pasos; el lodo que sale de la zona se
   contabiliza; la simulación termina cuando lo que se mueve en un paso es menor que
   $10^{-4}$ del volumen.

Se compila con Numba y solo recorre el rectángulo con lodo: una corrida tarda de menos de
un segundo a unos 10 s. `tests/test_automata.py` verifica conservación de masa (error
< 10⁻⁹), plano inclinado, cuenco, canal en V, borde absorbente, que v2 se detiene en
plano, y que más volumen ⇒ más alcance y más resistencia ⇒ menos alcance (13 pruebas).

## 4.3 Proceso iterativo del modelo

El registro completo, con figuras y tablas, está en `results/modelo/registro_iteraciones.md`.

| Versión | Cambio | Qué pasó | Qué motivó |
|---|---|---|---|
| v1.0 | Lodo sin resistencia, fuente a ojo | Se fue por la barranca del oeste | La fuente estaba al otro lado de una divisoria: se ajustó con el DEM |
| v1.2 | Fuente corregida, volumen en 100 pasos | Recorre 29.7 km y 61 % sale de la zona: se comporta como **agua** | Agregar resistencia (v2) |
| v2.0 | Espesor crítico (`h_min` / Bingham) | Hasta v1 se detenía a 2.5 km, atrapada en **hoyos del DSM** | Quitar el ruido del terreno |
| v2.1 | DEM sin hoyos | v1 llega al mar; v2 sí controla el alcance | Calibrar |
| v2.2 | Primera calibración | Ganaba la resistencia más baja y v1 le ganaba a v2 | Revisar el volumen y el dominio de validación |
| v2.3 | Volumen con el área de toda la barranca; validar solo en Las Lajas; objetivo penalizado | — | Calibración final |
| **v2.4** | **Calibración final** | Bingham, τ_y = 1000 Pa | Usar en el Monte Carlo (v3) |
| v3 | Monte Carlo con v2 calibrada | Mapas de probabilidad p1 y p2 | — |

![v1.2: sin resistencia el lodo recorre todo el sistema de ríos.](../../results/modelo/v1_lajas_5e+05.png){width=55%}

## 4.4 Mapa observado con Sentinel-2 (`src/sentinel/ndvi.py`)

Para cada periodo se compara el NDVI de la imagen inicial y la final dentro de un
corredor de 500 m alrededor del cauce de Las Lajas (hasta la confluencia):

| Clase | Significado | Regla |
|---|---|---|
| 2 | Cambio seguro: había vegetación y ya no | NDVI antes ≥ 0.4 y ΔNDVI ≥ 0.25 |
| 1 | Posible: desnudo al final, pero ya lo estaba | NDVI después < 0.2 |
| 0 | Vegetación | resto |
| 255 | Sin dato (nubes, sombras, fuera del corredor) | máscara SCL |

Se quitan manchas de menos de 5 píxeles y las que no tocan el cauce, y se pasa a la
cuadrícula de 30 m por mayoría. El corredor llegó a esa forma en cuatro iteraciones
(`results/sentinel/umbrales.md`): con el corredor de 38 km aparecían parcelas de caña
cosechadas como "cambio seguro"; la solución fue validar solo en Las Lajas.

**Hallazgo:** dentro de Las Lajas casi no hay cambio seguro en 2019 (≈ 0 km² en p1 y
0.01 km² en p2) y sí ~1 km² de cauce desnudo. La barranca ya estaba pelada desde 2018:
los lahares de 2019 pasan por un cauce sin vegetación que perder. Por eso la métrica
principal es la **versión amplia** (clases 1 y 2).

![Mapa observado en p2: cauce desnudo (clase 1) dentro del corredor de Las Lajas.](../../results/sentinel/observado_p2.png){width=50%}

## 4.5 Calibración (`src/modelo/calibrar.py`)

Búsqueda en cuadrícula de `relajacion` (0.2–0.8) × `h_min` (0.1–5 m) y × `τ_y`
(50–5000 Pa) con la tormenta mayor de p1 (61 mm, 6.3 × 10⁵ m³). Objetivo: **Jaccard
amplio penalizado**,

$$J_{pen} = \frac{|S \cap O|}{|S \cup O| + |S_{fuera}|}$$

que además del traslape cuenta como error el lodo simulado fuera del corredor (si no,
siempre gana el modelo que llega más lejos). Resultado (`results/modelo/calibracion_p1.png`):
máximo claro en **τ_y = 1000 Pa** (J_pen = 0.326) y en h_min = 0.5 m (0.312); la
relajación casi no influye. 1000 Pa está dentro de los esfuerzos de fluencia reportados
para flujos de detritos (10²–10⁴ Pa; Major y Pierson, 1992).

![Calibración con p1: sensibilidad del Jaccard penalizado a la resistencia.](../../results/modelo/calibracion_p1.png)

## 4.6 Monte Carlo (`src/montecarlo/correr.py`)

Cada corrida sortea, con distribución uniforme:

| Parámetro | Rango | Justificación (detalle en `src/montecarlo/rangos.py`) |
|---|---|---|
| `C` | 0.3 – 0.7 | La ceniza fresca sella el suelo (Jones et al., 2017; Pierson y Major, 2014) |
| `Cs` | 0.3 – 0.6 | Flujos hiperconcentrados a de detritos (Pierson y Costa, 1987; Pierson, 2005) |
| `factor_lluvia` | 1.0 – 1.5 | El modelo de 9 km suaviza los picos de tormentas convectivas |
| `relajacion` | 0.14 – 0.26 | ± 30 % de lo calibrado |
| `τ_y` | 700 – 1300 Pa | ± 30 % de lo calibrado |

Toma la tormenta mayor del periodo, calcula su volumen, corre la v2 y suma las celdas
alcanzadas: $P(\text{alcance}) = \text{corridas con lodo} / N$, con N = 500 y semilla fija.
**Suposición:** con la misma fuente y parámetros, un volumen mayor cubre lo que cubre uno
menor, así que la huella de la temporada ≈ la de la tormenta mayor.

