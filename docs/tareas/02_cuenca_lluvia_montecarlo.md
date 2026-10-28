# P2 – Cuenca, lluvia → volumen y Monte Carlo

**Responsable:** [nombre]
**Carpeta:** `src/inputs/` (archivos nuevos), `src/montecarlo/`, `results/montecarlo/`
**Lean primero:** [00_general.md](00_general.md) (contratos y cronograma)

## Objetivo

Tres cosas, en este orden:

1. **Cuenca:** usar el DEM para ubicar la barranca Las Lajas: dónde nace el lahar
   (la *fuente*), por dónde va el cauce y cuánta área le drena agua.
2. **Lluvia → volumen:** convertir la lluvia de Open-Meteo en m³ de lodo.
3. **Monte Carlo:** correr el modelo de P1 cientos de veces con parámetros aleatorios
   y producir el **mapa de probabilidad de alcance**, el resultado estrella del proyecto.

Lo que ya existe: `src/inputs/dem.py` (DEM listo) y `src/inputs/lluvia.py`
(lluvia horaria de Open-Meteo). Lean `data/README.md`, secciones 1 y 2.

---

## 1. Cuenca de Las Lajas → **🔗 Hito 1 (vie 30)**

Este es el primer entregable porque **P1, P3 y P4 dependen de él**. Prioridad máxima.

### Qué hacer

Script `src/inputs/cuenca.py`, con `python -m src.inputs.cuenca`:

1. **Dirección de flujo y acumulación** sobre el DEM. Recomendado: la librería
   [`pysheds`](https://github.com/mdbartos/pysheds) (agréguenla a `requirements.txt`):
   `fill_pits` → `fill_depressions` → `resolve_flats` → `flowdir` → `accumulation`.
2. **Ubicar la fuente** (dónde "nace" el lahar): un punto sobre la barranca Las Lajas
   donde el cauce ya está bien definido al salir del cono, entre ~1800 y 2500 m de
   altura. Para orientarse:
   - Las Lajas baja hacia el **sureste** del cráter (`CRATER_UTM` en `src/config.py`),
     pasa por El Rodeo y La Reina y cruza la RN-14.
   - En la imagen `data/raw/sentinel2/s2_20190326_rgb.png` se ven los depósitos grises.
   - El mapa del INSIVUMEH (`data/raw/insivumeh/fuego_lahares_escenario_B.tif`)
     marca el depósito piroclástico de 2018 en esa barranca.

   Escojan el punto a mano y luego **ajústenlo a la celda de mayor acumulación cercana**
   (*snap*), para que caiga justo en el cauce.
3. **Cuenca:** todas las celdas que drenan hacia la fuente → área en m².
4. **Cauce:** seguir la dirección de flujo desde la fuente hacia abajo hasta el borde
   de la zona. Guardar también la **distancia a lo largo del cauce** desde la fuente
   (P4 la usa para medir el error de alcance).

### Salidas (contrato)

| Archivo | Contenido |
|---|---|
| `data/processed/lajas_fuente.json` | `{"fila": .., "col": .., "x": .., "y": .., "z": .., "area_cuenca_m2": ..}` |
| `data/processed/lajas_cuenca.tif` | uint8, 1 = drena hacia la fuente |
| `data/processed/lajas_cauce.tif` | uint8, 1 = cauce desde la fuente hacia abajo |
| `data/processed/lajas_cauce_distancia.tif` | float32, metros a lo largo del cauce desde la fuente (NaN fuera del cauce) |
| `results/montecarlo/cuenca_lajas.png` | figura: sombreado + cuenca + cauce + fuente |

Todo en la cuadrícula del DEM (1280 × 1280).

### Cómo saber que está bien

- El cauce coincide con los depósitos grises de la imagen de Sentinel-2 del 26 de marzo.
- El cauce pasa cerca de El Rodeo y cruza la RN-14 (compárenlo con el mapa del INSIVUMEH).
- El área de la cuenca es de unos pocos km² (orden de magnitud; si da cientos, la fuente
  está demasiado abajo).

> La ubicación de la fuente es una **decisión de modelación**: documenten por qué la
> eligieron. Si da tiempo, prueben 2 o 3 fuentes y vean cuánto cambia el resultado.

---

## 2. Lluvia → volumen

### 2.1 Bajar la lluvia de los dos periodos

```bash
python -m src.inputs.lluvia --inicio 2019-03-26 --fin 2019-12-11
```

### 2.2 Separar tormentas

Script `src/inputs/volumen.py`:

```python
def tormentas(serie: pd.DataFrame, horas_secas: int = 6, umbral_mm: float = 20) -> pd.DataFrame:
    """Agrupa horas lluviosas en tormentas separadas por >= horas_secas sin lluvia.
    Devuelve las tormentas con lluvia total >= umbral_mm:
    columnas inicio, fin, lluvia_mm, max_1h_mm, periodo ("p1" o "p2")."""

def volumen_lahar(lluvia_mm: float, area_m2: float, C: float, Cs: float) -> float:
    """V_agua = P · A · C ;  V_lahar = V_agua / (1 − Cs)   (m³)"""
```

- `C`: coeficiente de escurrimiento (fracción de la lluvia que baja por la barranca).
- `Cs`: concentración de sedimento en volumen.
- El `umbral_mm` es una suposición: compárenlo con los días con lahar del catálogo de
  P4. Si hubo lahar con 15 mm, el umbral está alto.

### 2.3 Rangos de los parámetros (literatura)

Su tarea es **justificar con fuentes** estos rangos iniciales (pueden cambiarlos):

| Parámetro | Rango inicial | Justificación a buscar |
|---|---|---|
| `C` | 0.3 – 0.7 | La ceniza fresca impermeabiliza el suelo → C alto en volcanes activos |
| `Cs` | 0.3 – 0.6 | Flujos hiperconcentrados ~20–60 %, flujos de detritos > 60 % (Pierson & Costa; Vallance & Iverson) |
| `factor_lluvia` | 1.0 – 1.5 | Open-Meteo (9 km) subestima las tormentas cortas en montaña |
| `h_min` / `tau_y`, `relajacion` | ± 30 % alrededor de lo calibrado por P1 | Incertidumbre de la calibración |

Fuentes por dónde empezar: los papers de la sección 12 del plan (sobre todo la tesis de
Buondonno, que trae análisis de lluvia en Fuego).

---

## 3. Monte Carlo

Script `src/montecarlo/correr.py`:

```python
def monte_carlo(periodo: str, n: int, rangos: dict, semilla: int = 42) -> tuple[np.ndarray, pd.DataFrame]:
    """Devuelve (prob, muestras):
    prob: (1280, 1280) float, fracción de corridas en que cada celda fue alcanzada.
    muestras: una fila por corrida con los parámetros sorteados y el alcance obtenido."""
```

### Cada corrida (realización)

1. Sortear `C`, `Cs`, `factor_lluvia`, `h_min`, `relajacion` (uniformes en sus rangos).
2. Tomar la **tormenta más grande del periodo** → `volumen_lahar(P · factor, A, C, Cs)`.
3. `simular(dem, fuente, volumen, params)` (función de P1).
4. Sumar `resultado.alcanzado` al contador.

Al final: `prob = contador / n`.

> **¿Por qué solo la tormenta más grande?** Queremos el área que tocó el lodo en toda la
> temporada. Con la misma fuente y los mismos parámetros, un volumen mayor cubre todo lo
> que cubre uno menor (P1 lo verifica en su prueba de sensibilidad). Entonces la unión
> de todas las tormentas ≈ la huella de la mayor. Así ahorramos ~20 veces el cómputo.
> **Esta suposición va en el documento.**

### Detalles

- **Semilla fija** para que sea reproducible.
- **Convergencia:** grafiquen cómo cambia el mapa de probabilidad al aumentar N
  (ej. la diferencia máxima entre N y N/2). Si se estabiliza, N es suficiente. Es una
  figura clásica de Monte Carlo y le gusta a cualquier profe de simulación.
- Tiempo: N = 500 × ~5 s ≈ 40 min. Córranlo en segundo plano. Prueben primero con N = 20.
- Mientras P1 no tenga `simular()`, usen un **stub**: un círculo alrededor de la fuente
  con radio proporcional a `volumen ** (1/3)`.

### Salidas

| Archivo | Contenido |
|---|---|
| `results/montecarlo/prob_p1.tif`, `prob_p2.tif` | mapas de probabilidad (cuadrícula del DEM) |
| `results/montecarlo/muestras_p1.csv`, `muestras_p2.csv` | parámetros por corrida |
| `results/montecarlo/convergencia.png` | figura de convergencia |
| `results/montecarlo/prob_p2.png` | mapa de probabilidad sobre el sombreado |
| `results/montecarlo/tormentas_2019.csv` | tormentas detectadas y su volumen central |

---

## 4. Tu cronograma

| Día | Tarea |
|---|---|
| **Jue 29** | `pysheds`, dirección de flujo y acumulación; ubicar la fuente a ojo |
| **Vie 30** | **🔗 Hito 1:** `cuenca.py` completo (fuente, cuenca, cauce, distancia) + figura; avisar al grupo. Bajar la lluvia de los dos periodos |
| **Sáb 31** | `volumen.py` (tormentas + volumen); rangos de la literatura; `correr.py` con el stub y luego con el `simular` de P1 |
| **Dom 1** | **🔗 Hito 2:** recibir los parámetros calibrados de P1 → Monte Carlo de p1 y p2 (N = 500) |
| **Lun 2** | Convergencia, figuras; escribir las secciones "Datos: DEM y lluvia" y "Lluvia → volumen y Monte Carlo" |
| **Mar 3** | Revisar el documento |

## 5. Dependencias

| Necesito | De | Mientras tanto |
|---|---|---|
| `simular()` | P1 (v1 el vie 30, v2 el sáb 31) | Stub del círculo |
| Parámetros calibrados | P1 (dom 1) | Rangos amplios |
| Días con lahar en 2019 | P4 (catálogo) | Umbral de 20 mm |

| Doy | A | Cuándo |
|---|---|---|
| `lajas_fuente.json`, cuenca, cauce, distancia | P1, P3, P4 | **vie 30** |
| Volúmenes de las tormentas de p1 | P1 (calibración) | sáb 31 |
| `prob_p1.tif`, `prob_p2.tif` | P4 | dom 1 – lun 2 |

## 6. Limitaciones para documentar

- La celda de lluvia de 9 km promedia todo el cono.
- La fórmula de volumen ignora la disponibilidad real de sedimento suelto y la infiltración variable.
- La suposición de "tormenta más grande = huella de la temporada".
- La fuente es fija (en la realidad los lahares se forman en varios puntos de la barranca).
