# Registro de iteraciones del modelo

Bitácora del proceso iterativo (insumo para la sección "Modelo y proceso
iterativo" del documento). Cada entrada dice qué se cambió, por qué y qué se observó.

Todas las corridas: Las Lajas, V = 5 × 10⁵ m³, relajación 0.5, DEM Copernicus 30 m.
Figuras en esta misma carpeta; se regeneran con `python -m src.modelo.demo …`.

---

## v1.0 – Fuente en (285, 790), lodo de golpe

`--fuente 285,790 --pasos-fuente 1` (la figura que se guardó usa `--pasos-fuente 100`:
[`v1_lajas_5e+05_fuente_oeste.png`](v1_lajas_5e+05_fuente_oeste.png))

- **Qué hicimos:** primera versión del autómata (minimización de diferencias, 8
  vecinos, todo el lodo se mueve). Fuente puesta a ojo donde el depósito gris de Las
  Lajas sale del cono, a 2089 m.
- **Qué pasó:** el lodo **no bajó por Las Lajas**. Se fue por la barranca paralela del
  oeste y se detuvo a 10.8 km (530 m de altura), atrapado en hoyos del terreno.
- **Por qué:** la fuente estaba del **otro lado de una divisoria de aguas**. Al rastrear
  el flujo en el DEM con las depresiones rellenadas, casi todos los puntos cercanos
  drenan al oeste; solo desde (290, 810) hacia abajo el cauce sigue la banda gris, pasa
  por La Reunión y junto a El Rodeo (ubicados con el mapa del INSIVUMEH).
- **Lección:** la ubicación de la fuente es crítica cerca del cono, donde las barrancas
  nacen juntas. El DEM es de antes de 2018: los depósitos de 2018 pueden haber cambiado
  la divisoria en la realidad.

## v1.1 – Fuente en (294, 822), lodo de golpe

`--pasos-fuente 1 --etiqueta de_golpe` → [`v1_lajas_5e+05_de_golpe.png`](v1_lajas_5e+05_de_golpe.png)

- **Qué cambiamos:** fuente a 1731 m, unos 380 m cauce abajo de la divisoria.
- **Qué pasó:** el lodo sigue Las Lajas, pasa junto a Escuintla y continúa por el
  Guacalate hasta el borde sur de la zona: **29.7 km de alcance, 61 % del volumen salió
  de la zona**, 9105 pasos (76 s).
- **Problema:** espesor máximo de **415 m** en la fuente: soltar 5 × 10⁵ m³ en una sola
  celda de 900 m² crea una "torre" de 555 m. Es un artefacto numérico.

## v1.2 – Fuente en (294, 822), lodo en 100 pasos ✅ (v1 final)

`python -m src.modelo.demo --version v1 --volumen 5e5` → [`v1_lajas_5e+05.png`](v1_lajas_5e+05.png)

- **Qué cambiamos:** el volumen se suelta durante 100 pasos (un hidrograma simple).
  Ahora es el valor por defecto (`Parametros.pasos_fuente = 100`).
- **Qué pasó:** mismo recorrido y alcance (29.7 km, 61 % fuera), espesor máximo de
  **28.5 m** (razonable para el fondo de una barranca), 3.09 km² con más de 10 cm de lodo.
- **Conclusión de v1:** se comporta como **agua**: no tiene ningún mecanismo para
  detenerse en pendiente, así que recorre todo el sistema de ríos hasta salir de la
  zona. Los lahares reales de Las Lajas se depositan mucho antes. **Esto motiva v2:**
  agregar la resistencia del lodo (espesor mínimo / Bingham).

### Otras observaciones de v1

- **El DSM tiene hoyos** (árboles, casas): en v1.0 el lodo se quedó atrapado en ellos.
  En el Monte Carlo esto actúa como una fricción artificial que no controlamos.
- **Rendimiento:** ~75 s por corrida cuando el lodo recorre toda la zona. v2 debería ser
  más rápida porque se detiene antes; aun así hay que optimizar (recorrer solo las
  celdas con lodo) para llegar a menos de 5 s.
- **Pruebas en terrenos inventados** (`tests/test_automata.py`, 8 pruebas): conservación
  de masa, plano inclinado, cuenco, plano horizontal, canal en V, borde absorbente y
  más volumen ⇒ más alcance. Todas pasan.

| Versión | Fuente | Liberación | Alcance | % fuera | h máx | Pasos | Tiempo |
|---|---|---|---|---|---|---|---|
| v1.0 | (285, 790) | 100 pasos | 10.8 km (otra barranca) | 0 % | 29 m | 2472 | 16 s |
| v1.1 | (294, 822) | de golpe | 29.7 km | 61 % | 415 m | 9105 | 76 s |
| v1.2 | (294, 822) | 100 pasos | 29.7 km | 61 % | 28.5 m | 9123 | 74 s |

---

## v2.0 – Resistencia del lodo (espesor crítico), DEM original

`simular(..., version="v2")`: una celda solo cede el lodo que pasa de un espesor crítico
`h_crit = max(h_min, τ_y / (ρ g sen θ))` (`h_min` = versión simple, `τ_y` = Bingham).
Pruebas nuevas en `tests/test_automata.py`: v2 se detiene en plano horizontal, conserva la
masa, más `h_min` ⇒ menos alcance, y Bingham baja una rampa pero se detiene en lo plano.

- **Qué pasó en Las Lajas:** con el volumen de la tormenta mayor de p1 (1.8 × 10⁴ m³,
  calculado con la cuenca arriba de la fuente, 0.32 km²) **hasta la v1 se detiene a
  2.5 km**, atrapada en los hoyos del DSM. La resistencia de v2 no tiene nada que
  controlar: el que detiene el lodo es el ruido del terreno.
- **Lección:** antes de calibrar la física hay que quitar lo que la imita.

## v2.1 – Terreno sin hoyos

`src/modelo/terreno.py`: el autómata corre sobre el DEM con hoyos y depresiones rellenados
(mismo acondicionamiento que la cuenca).

| Corrida (V = 5 × 10⁴ m³) | DEM original | DEM relleno |
|---|---|---|
| v1 | 2.6 km, 0 % fuera | 38.6 km, 100 % sale de la zona |
| v2, `h_min` = 1 m | 0.6 km | 0.6 km |
| v2, `τ_y` = 1000 Pa | 1.5 km | 1.8 km |

Ahora v1 se comporta como agua (llega al mar) y v2 sí controla el alcance.

## v2.2 – Primera calibración: el objetivo estaba mal

Cuadrícula de `relajacion` × `h_min` y `relajacion` × `τ_y` contra p1, eligiendo por el
Jaccard promedio (estricta + amplia). **Ganó el valor más bajo de la cuadrícula
(τ_y = 20 Pa) y v1 le ganó a v2.** Dos razones:

1. Pasando el km 7.4 el cauce entra al **río Guacalate** (el área drenada salta de 11 a
   124 km²). Los cambios "observados" entre los km 8 y 36 son del Guacalate (crecidas,
   caña de azúcar), no de los lahares de Las Lajas, y premiaban llegar lejos.
2. El volumen salía de la cuenca arriba de la fuente (0.32 km²): para llegar a donde
   se ven cambios hacía falta una resistencia irrealmente baja.

## v2.3 – Volumen y dominio de validación corregidos

- **Volumen:** el área de escurrimiento es toda la barranca hasta la confluencia
  (11.3 km², `area_lajas_m2` en `lajas_fuente.json`): el lahar se alimenta del agua de
  toda la barranca en su camino. Tormenta mayor de p1: 6.3 × 10⁵ m³; de p2: 1.5 × 10⁶ m³,
  del orden de lo reportado para lahares de Fuego.
- **Dominio:** la máscara observada solo cubre Las Lajas hasta la confluencia.
- **Objetivo:** Jaccard amplio **penalizado** (el lodo fuera del corredor cuenta como
  error). Dentro de Las Lajas casi no hay clase 2 en 2019 (la barranca está pelada desde
  2018), así que la versión estricta no sirve para calibrar.

## v2.4 – Calibración final ✅ (v2 final)

`python -m src.modelo.calibrar` → `calibracion_p1.csv`, `calibracion_p1.png`,
`parametros_calibrados.json`.

- **Mejor:** Bingham, `τ_y` = 1000 Pa, `relajacion` = 0.2 (Jaccard penalizado 0.326,
  Jaccard amplio 0.456). Con `h_min` el mejor fue 0.5 m (0.312). 1000 Pa está dentro de
  los esfuerzos de fluencia reportados para flujos de detritos (10²–10⁴ Pa).
- En `calibracion_p1.png` las curvas de las cuatro `relajacion` casi se enciman: es un
  parámetro numérico (qué fracción del exceso se mueve por paso) y casi no cambia el
  resultado. Ganó 0.2 por milésimas. Lo que sí importa es la resistencia: hay un máximo
  claro en `τ_y` = 1000 Pa y en `h_min` = 0.5 m; con menos el lodo sigue al Guacalate,
  con más se queda corto.

`python -m src.modelo.calibrar --versiones` → `metricas_versiones.csv`:

| Versión | Periodo | Volumen | Alcance por el cauce | Jaccard penalizado | Jaccard amplio | Fuera del corredor |
|---|---|---|---|---|---|---|
| v1 | p1 (calibración) | 6.3 × 10⁵ m³ | 38.6 km | 0.124 | 0.409 | 80 % |
| **v2** | p1 (calibración) | 6.3 × 10⁵ m³ | **8.3 km** | **0.326** | 0.456 | 38 % |
| v1 | p2 (prueba) | 1.5 × 10⁶ m³ | 38.6 km | 0.114 | 0.451 | 80 % |
| **v2** | p2 (prueba) | 1.5 × 10⁶ m³ | **14.1 km** | **0.227** | 0.437 | 54 % |

- **Conclusión de v2:** con la resistencia el lodo se detiene poco después de la
  confluencia en vez de llegar al mar, y en la prueba (p2, sin tocar los parámetros)
  el Jaccard penalizado duplica al de v1. El Jaccard amplio casi no distingue las
  versiones porque el cauce desnudo de 2018 llega hasta la confluencia: la imagen
  muestra por dónde **puede** pasar el lodo, no hasta dónde llegó.

## v3 – Lluvia y Monte Carlo

v3 es la v2 calibrada dentro del Monte Carlo (`src/montecarlo/correr.py`): cada corrida
sortea `C`, `Cs`, `factor_lluvia`, `relajacion` (0.14–0.26) y `τ_y` (700–1300 Pa), con el
volumen de la tormenta mayor de cada periodo. Resultados en `results/montecarlo/`.
