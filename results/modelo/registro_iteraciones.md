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
