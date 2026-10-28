# P4 – Validación, puntos de referencia y documento final

**Responsable:** [nombre]
**Carpeta:** `src/validacion/` (archivos nuevos), `tests/test_metricas.py`, `results/validacion/`, `docs/informe/`
**Lean primero:** [00_general.md](00_general.md) (contratos y cronograma)

## Objetivo

Responder la pregunta que más le importa al profe: **¿el modelo predice la realidad?**

1. **Métricas:** las funciones que comparan lo simulado con lo observado.
2. **Referencias reales:** catálogo de eventos, puntos clave y el mapa de amenaza del INSIVUMEH.
3. **Evaluación:** calibración (con P1) y prueba final.
4. **Documento final:** armarlo e integrarlo.

Lo que ya existe (lean `data/README.md`, secciones 4 y 5):
- `data/raw/insivumeh/fuego_lahares_escenario_B.tif`: mapa de amenaza georreferenciado.
- `data/catalogo_lahares.csv`: 3 boletines verificados (Ceniza, 2024–2026).

---

## 1. Métricas → **🔗 Hito 1 (vie 30)**

Script `src/validacion/metricas.py`. Lo usan P1 (calibración) y todos en los resultados.

```python
def evaluar(sim: np.ndarray, obs: np.ndarray, distancia: np.ndarray) -> dict:
    """sim: bool (alcanzado por el modelo). obs: uint8 de P3 (0/1/2/255).
    distancia: lajas_cauce_distancia.tif de P2.
    Devuelve las métricas en sus dos versiones, 'estricta' y 'amplia'."""

def jaccard(sim, obs, validos) -> float          # |S ∩ O| / |S ∪ O| dentro de validos
def confusion(sim, obs, validos) -> dict          # VP, FP, FN, VN, precisión, sensibilidad, F1
def alcance_m(mascara, distancia) -> float        # distancia máxima por el cauce con lodo
def error_alcance(sim, obs, distancia) -> float   # alcance_sim − alcance_obs, en m
def puntos_clave(mapa, puntos: pd.DataFrame, umbral=0.5) -> pd.DataFrame
    # mapa puede ser bool (una corrida) o probabilidad (Monte Carlo)
```

### Cómo usar las clases de P3

| Versión | Positivos observados | Se ignora | Válidos |
|---|---|---|---|
| **Estricta** | clase 2 (cambio seguro) | clase 1 (no cuenta ni como acierto ni como error) | clases 0 y 2 |
| **Amplia** | clases 1 y 2 | — | clases 0, 1 y 2 |

La clase 255 (nube, fuera del corredor) **nunca** cuenta.

> **Ojo:** como fuera del corredor todo es 255, si el modelo se desborda a más de
> 500 m del cauce no se penaliza. Reporten también el **% del área simulada que cae
> fuera del corredor**: si es alto, hay un problema.

### Probarlas antes de tener datos reales

`tests/test_metricas.py` con dos círculos inventados:
- Círculos idénticos → Jaccard = 1.
- Sin traslape → Jaccard = 0.
- Un círculo dentro del otro con la mitad de área → Jaccard = 0.5.
- Clase 1 en la versión estricta → no cambia el resultado.

---

## 2. Referencias reales

### 2.1 Puntos clave → **🔗 Hito 1 (vie 30)**

`data/puntos_clave.csv` (sí va a git):

```
nombre,x,y,tipo,barranca,esperado_p1,esperado_p2,fuente,notas
```

- Abran `fuego_lahares_escenario_B.tif` en **QGIS** y tomen las coordenadas (UTM 15N)
  de los lugares que marca: **El Rodeo, La Reina, San Miguel Los Lotes, el puente de
  Las Lajas en la RN-14, el cruce con la CA-2**.
- Agreguen **2 o 3 puntos de control** que **no** deberían alcanzarse (ej. La Trinidad o
  Finca El Zapote, que están en otra barranca). Sirven para detectar falsas alarmas.
- `esperado_p1` / `esperado_p2`: ¿llegó el lodo ahí en ese periodo? Sale del catálogo
  (2.2) o de la máscara de P3. Si no se sabe, dejen vacío.

### 2.2 Catálogo de lahares de 2019

Llenen `data/catalogo_lahares.csv` con los lahares de **Las Lajas en 2019** (fecha,
intensidad, hasta dónde llegó, si cerraron la RN-14 o el puente…). Fuentes:

1. **Smithsonian Global Volcanism Program**: volcano.si.edu, Fuego (342090), reportes
   semanales. Resumen los boletines del INSIVUMEH con fecha y barranca. Es la mejor fuente
   archivada. Estaba caído el 27 de octubre; reintenten.
2. **X del INSIVUMEH** (@insivumehgt): búsqueda avanzada `from:insivumehgt lahar Lajas`
   con fechas de 2019.
3. **CONRED** (conred.gob.gt) y noticias (Prensa Libre, Soy502) para el alcance:
   "cierre de la RN-14", "puente Las Lajas", etc.

Para qué sirve:
- P2 valida su umbral de lluvia (¿los días con lahar tuvieron lluvia fuerte?).
- Llena `esperado_p1/p2` de los puntos clave.
- Agrega una prueba independiente de Sentinel-2.

### 2.3 Mapa de amenaza del INSIVUMEH clasificado

Script `src/validacion/mapa_amenaza.py` → `data/processed/amenaza_insivumeh_B.tif`
(uint8: 0 = nada, 1 = baja/amarillo, 2 = media/naranja, 3 = alta/rojo; cuadrícula del DEM).

1. Leer el RGB (5.45 m/píxel).
2. Muestrear los colores reales de cada zona (hagan clic en QGIS o con matplotlib) y
   clasificar cada píxel por **distancia de color** al rojo, naranja y amarillo.
3. Quitar texto, líneas de carreteras y el rayado del depósito piroclástico con un
   filtro morfológico (apertura).
4. Pasar a la cuadrícula de 30 m tomando la clase **máxima** que cubra al menos la
   mitad de la celda (ver el ejemplo de `reproject` en `00_general.md`).

**Cómo compararlo:** el mapa es un **escenario** de lluvias muy intensas, no un evento
real. No esperamos que coincida con un periodo de 2019. Comparen la simulación con
**volumen alto** (tormenta máxima × factores altos) contra la zona coloreada de Las Lajas:
- ¿Qué % del área simulada cae dentro de la zona de amenaza?
- ¿Qué % de la zona de amenaza cubre la simulación?

> Los bordes en sierra de ese mapa se parecen a los de **LAHARZ**. Si es así, esta
> comparación **reemplaza** implementar LAHARZ nosotros (lo primero que se recorta).
> Si les sobra tiempo: `A = 0.05 · V^(2/3)`, `B = 200 · V^(2/3)` (Iverson et al., 1998).

---

## 3. Evaluación

### 3.1 Calibración (🔗 Hito 2, dom 1, con P1)

P1 corre la búsqueda de parámetros y usa su `evaluar()` contra
`observado_lajas_2019_p1.tif`. Ustedes revisan que se use bien (versión estricta y
amplia, sin datos de p2).

### 3.2 Prueba final (lun 2)

Con los parámetros **ya fijos**:

| Prueba | Qué se compara | Métricas |
|---|---|---|
| **Sentinel-2 p2** | `prob_p2.tif` (P2) con umbral 0.5 vs. `observado_lajas_2019_p2.tif` | Jaccard, F1, error de alcance (estricta y amplia) |
| **Puntos clave** | `prob_p2.tif` en cada punto vs. `esperado_p2` | aciertos, falsas alarmas, fallos |
| **INSIVUMEH** | corrida de volumen alto vs. `amenaza_insivumeh_B.tif` | % de traslape en ambos sentidos |
| **v1 vs. v2** | las dos versiones contra p1 y p2 | tabla de mejora (proceso iterativo) |
| *Opcional* | fiabilidad: de las celdas con prob ≈ 0.7, ¿~70 % se observaron? | curva de fiabilidad |

**Salidas:** `results/validacion/tabla_metricas.csv`, `results/validacion/puntos_clave.csv`
y figuras (simulado vs. observado con colores VP / FP / FN).

---

## 4. Documento final

Ustedes son quienes **integran**. Desde el **vie 30**:

1. Confirmen con el profe el **formato** de entrega (PDF, Word, LaTeX, notebook…).
2. Creen el esqueleto en `docs/informe/` con las secciones y quién escribe cada una
   (tabla de la sección 6 de `00_general.md`).
3. Escriban ustedes: **introducción** (problema, qué es un lahar, por qué importa;
   San Miguel Los Lotes 2018 como contexto, aclarando que fue un flujo piroclástico),
   **validación** y **conclusiones**.
4. El **lun 2** junten las secciones de todos; el **mar 3** revisión final y entrega.

Ideas de figuras para la introducción: la imagen RGB de marzo de 2019 (depósitos
visibles) y el mapa de amenaza del INSIVUMEH.

---

## 5. Tu cronograma

| Día | Tarea |
|---|---|
| **Jue 29** | `metricas.py` + pruebas con círculos; empezar el catálogo; preguntar el formato |
| **Vie 30** | **🔗 Hito 1:** métricas listas para P1; `puntos_clave.csv`; esqueleto del informe |
| **Sáb 31** | `mapa_amenaza.py`; catálogo de 2019; llenar `esperado_p1/p2` |
| **Dom 1** | **🔗 Hito 2:** calibración con P1 |
| **Lun 2** | Prueba final; tablas y figuras; escribir sus secciones; juntar las de todos |
| **Mar 3** | Revisión final y **entrega** |

## 6. Dependencias

| Necesito | De | Mientras tanto |
|---|---|---|
| `observado_lajas_2019_p1/p2.tif` | P3 (vie 30 / sáb 31) | Círculos de prueba |
| `lajas_cauce_distancia.tif`, `lajas_cuenca.tif` | P2 (vie 30) | Probar `alcance_m` con una línea recta |
| `prob_p1/p2.tif` | P2 (dom 1 – lun 2) | Una corrida suelta de P1 |
| Secciones del documento | todos (lun 2) | Esqueleto con los títulos |

| Doy | A | Cuándo |
|---|---|---|
| `metricas.py` (`evaluar`, `jaccard`…) | P1 | **vie 30** |
| Días con lahar de 2019 | P2 (umbral de lluvia) | sáb 31 |
| Documento integrado | profe | mar 3 |

## 7. Limitaciones para documentar

- La "verdad" (Sentinel-2) tiene incertidumbre propia: por eso hay versión estricta y amplia.
- El mapa del INSIVUMEH es un escenario, no un evento.
- Pocos eventos de prueba: un solo periodo (p2) en una sola barranca.
- El corredor de 500 m esconde los desbordes grandes (por eso el % fuera del corredor).
