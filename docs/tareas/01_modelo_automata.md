# P1 – Modelo: autómata celular de lahares

**Responsable:** [nombre]
**Carpeta:** `src/modelo/`, `tests/`, `results/modelo/`
**Lean primero:** [00_general.md](00_general.md) (contratos y cronograma)

## Objetivo

Construir la función que, dado el terreno, el punto donde nace el lahar y un volumen
de lodo, simula hacia dónde fluye el lodo y dónde se detiene. Es el **corazón** del
proyecto: P2 la llama miles de veces en el Monte Carlo y P4 compara su resultado con
la realidad.

Además, esta parte **demuestra el proceso iterativo** que pide el reglamento: v1 → v2 → v3,
cada versión con métricas y la razón del cambio.

---

## 1. Lo que hay que entregar

### 1.1 La función (contrato con P2 y P4)

```python
# src/modelo/automata.py
from dataclasses import dataclass
import numpy as np

@dataclass
class Parametros:
    relajacion: float = 0.5     # fracción del exceso que se mueve por paso (0–1]
    h_min: float = 0.0          # m, espesor que se queda quieto (v2, versión simple)
    tau_y: float = 0.0          # Pa, resistencia del lodo (v2, versión física)
    densidad: float = 2000.0    # kg/m³ de la mezcla
    max_pasos: int = 20_000
    tol: float = 1e-4           # se detiene si se mueve menos de tol × volumen por paso

@dataclass
class Resultado:
    h_final: np.ndarray         # (1280, 1280) espesor final de lodo, m
    h_max: np.ndarray           # espesor máximo alcanzado en cada celda, m
    alcanzado: np.ndarray       # bool: h_max > 0.1 m
    paso_llegada: np.ndarray    # int: primer paso con lodo (-1 si nunca); para el extra
    pasos: int                  # pasos hasta detenerse
    volumen_perdido: float      # m³ que salieron por el borde de la zona

def simular(dem: np.ndarray, fuente: tuple[int, int], volumen_m3: float,
            params: Parametros, version: str = "v2", res: float = 30.0) -> Resultado:
    ...
```

- `dem` es el arreglo completo de 1280 × 1280. Internamente pueden recortar, pero
  **lo que devuelven es siempre del tamaño completo** (contrato de cuadrícula).
- `fuente` viene de `data/processed/lajas_fuente.json` (lo genera P2).
- Debe ser **rápida**: P2 va a correrla ~500 veces. Meta: **menos de 5 s por corrida**.

### 1.2 Las tres versiones

| Versión | Regla | Qué esperamos | Para qué sirve en el documento |
|---|---|---|---|
| **v1** | Todo el lodo se mueve hacia vecinos más bajos hasta que la superficie queda "plana". Se comporta como agua | Llega **demasiado lejos** | Línea base: demuestra por qué hace falta física del lodo |
| **v2** | El lodo tiene **resistencia**: una celda solo cede lodo por encima de un espesor crítico. Se detiene en zonas planas | Alcance cercano a la realidad | El modelo "bueno" que se calibra |
| **v3** | Igual que v2, pero el volumen viene de la **lluvia** y los parámetros son **aleatorios** (Monte Carlo) | Mapa de probabilidad | Lo arma P2 usando la v2; aquí solo nos aseguramos de que v2 lo soporte |

### 1.3 Otros entregables

- `tests/test_automata.py`: pruebas de cordura (sección 4).
- `python -m src.modelo.demo --version v1|v2`: corre Las Lajas con un volumen fijo y guarda
  `results/modelo/<version>_lajas.png` (mapa de espesor sobre el sombreado del DEM).
- `results/modelo/metricas_versiones.csv`: una fila por versión con Jaccard, error de
  alcance y parámetros (las métricas las da P4).
- Sección del documento: **"Modelo y proceso iterativo"**.

---

## 2. El algoritmo

Base: **minimización de diferencias** de Di Gregorio & Serra (1999), la idea detrás de
los modelos SCIDDICA para flujos de detritos. Versión simplificada:

**Estado de cada celda:** `z` (terreno, fijo) y `h` (lodo). Superficie libre: `H = z + h`.

**Vecindad:** Moore, 8 vecinos. Las diagonales están a `√2 · 30 m`.

**En cada paso, para cada celda `i` con lodo:**

1. Calcular cuánto lodo **puede** moverse:
   - v1: `h_mov = h_i`
   - v2 simple: `h_mov = max(0, h_i − h_min)`
   - v2 física (Bingham): `h_crit = τ_y / (ρ · g · sen θ)`, con `θ` = pendiente de la
     superficie libre hacia el vecino más bajo; `h_mov = max(0, h_i − h_crit)`.
     En pendiente fuerte `h_crit` es pequeño (fluye); en plano es enorme (se detiene).
2. Vecinos "receptores": los `j` con `H_j < H_i`.
3. Total que sale, limitado para que no oscile:
   `salida = relajacion · min(h_mov, (H_i − min_j H_j) / 2)`
   (nunca más de la mitad de la diferencia con el vecino más bajo).
4. Repartir `salida` entre los receptores, proporcional a `(H_i − H_j) / d_ij`.

**Fuente:** en v1 se pone todo el volumen de golpe en la celda fuente
(`h = V / 900`). Opcional: soltarlo durante los primeros K pasos (más realista).

**Bordes:** el lodo que sale de la zona se cuenta en `volumen_perdido` y desaparece.

**Fin:** cuando lo que se mueve en un paso es menor que `tol · V`, o en `max_pasos`.

### Rendimiento

1280 × 1280 = 1.6 millones de celdas: recorrerlas todas en cada paso es lento.

1. **Recortar** a un corredor alrededor del cauce de Las Lajas (de `lajas_cauce.tif`,
   con 1–2 km de margen). Quedan ~200 mil celdas.
2. Usar **Numba** (`@njit`) con un ciclo sobre las celdas activas, o NumPy vectorizado
   con desplazamientos de arreglos (`np.roll` / slicing) para los 8 vecinos.
3. Midan: `time` de una corrida. Si pasa de 5 s, avisen a P2 para bajar N del Monte Carlo.

### Ojo

- **Conservación de masa:** `h.sum() · 900 + volumen_perdido == volumen_m3` en todo
  momento. Si no se cumple, hay un error.
- El DEM es un DSM (incluye árboles): puede haber "muros" falsos de ~20 m en las
  orillas del cauce. Si el lodo se queda atorado raro, ese puede ser el motivo.
- Los **pasos no son segundos**. Para el tiempo de llegada (extra) habría que
  calibrar la velocidad; si no da tiempo, se reporta solo el orden de llegada.

---

## 3. Calibración (Hito 2, con P4)

Con el periodo **p1** (2019-03-26 → 2019-07-04):

1. P2 da el volumen de los eventos de lluvia de p1.
2. Búsqueda en cuadrícula de `relajacion` × (`h_min` o `tau_y`):
   - `relajacion`: 0.2, 0.4, 0.6, 0.8
   - `h_min`: 0.5, 1, 2, 3, 5 m (o `tau_y`: 200, 500, 1000, 2000, 5000 Pa; confirmar
     rangos con P2, que revisa la literatura)
3. Para cada combinación: simular y calcular el Jaccard contra
   `observado_lajas_2019_p1.tif` (función de P4).
4. Elegir la mejor combinación. **Esos parámetros quedan fijos** para la prueba con p2.
5. Guardar la tabla completa (`results/modelo/calibracion_p1.csv`) y una figura de
   Jaccard vs. parámetros: muestra la sensibilidad del modelo y queda muy bien en el documento.

---

## 4. Cómo saber que funciona (pruebas)

Antes de usar el volcán real, prueben en terrenos inventados (`tests/test_automata.py`):

| Prueba | Terreno | Debe pasar |
|---|---|---|
| Conservación | cualquiera | masa total constante (± 1e-6) |
| Plano inclinado | `z = −x` | el lodo avanza en dirección de la pendiente |
| Cuenco | parábola `z = x² + y²` | el lodo termina en el fondo y se queda ahí |
| Plano horizontal (v2) | `z = 0` | con `h_min > 0` el lodo se detiene; con v1 se esparce |
| Canal en V | valle con pendiente | el lodo sigue el canal y no se sale por los lados |
| Sensibilidad | volcán real | más volumen ⇒ más alcance; más `h_min` ⇒ menos alcance |

---

## 5. Tu cronograma

| Día | Tarea |
|---|---|
| **Jue 29** | Estructura `src/modelo/`; v1 en terrenos de prueba; pruebas de conservación y cuenco |
| **Vie 30** | v1 sobre el DEM real con la fuente de P2 (o una a mano mientras tanto); recorte y rendimiento. **🔗 Hito 1:** v1 en Las Lajas |
| **Sáb 31** | v2 (`h_min` primero, Bingham si da tiempo); figura v1 vs. v2; pasar `simular` a P2 |
| **Dom 1** | **🔗 Hito 2:** calibración con P4 sobre p1 |
| **Lun 2** | Correr la prueba con p2 (parámetros fijos); escribir la sección del modelo |
| **Mar 3** | Revisar el documento |

## 6. Dependencias

| Necesito | De | Mientras tanto |
|---|---|---|
| `lajas_fuente.json`, `lajas_cauce.tif` | P2 (vie 30) | Fuente a mano: la celda más alta del canal SE del cráter, viéndola en la vista previa del DEM |
| Volúmenes de los eventos de p1 | P2 (sáb 31) | Volúmenes fijos de prueba: 1e5, 5e5, 1e6 m³ |
| `jaccard()` y máscara observada | P4 y P3 (dom 1) | Comparación a ojo con la imagen RGB de Sentinel-2 |

| Doy | A | Cuándo |
|---|---|---|
| `simular()` v1 (aunque sea lenta) | P2 | vie 30 |
| `simular()` v2 rápida | P2 | sáb 31 |
| Parámetros calibrados | P2 (rangos del Monte Carlo) y P4 | dom 1 |

## 7. Para el documento (proceso iterativo)

Por cada versión, guarden:
- Qué cambió y **por qué** (qué falla de la versión anterior lo motivó).
- Figura del resultado en Las Lajas.
- Métricas contra p1 (Jaccard, error de alcance).

Ese registro **es** la evidencia del proceso iterativo; no lo dejen para el final.
