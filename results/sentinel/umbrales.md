# Umbrales del mapa observado (Sentinel-2) y por qué

Script: `src/sentinel/ndvi.py`. Figuras: `ndvi_<periodo>.png`, `observado_<periodo>.png`,
`histogramas.png`.

## Umbrales (congelados antes de calibrar el modelo)

| Umbral | Valor | Para qué |
|---|---|---|
| `NDVI_VEGETACION` | 0.4 | Antes del periodo había vegetación |
| `DELTA_NDVI` | 0.25 | Pérdida mínima de NDVI para "cambio seguro" (clase 2) |
| `NDVI_DESNUDO` | 0.2 | Suelo desnudo al final del periodo (clase 1) |
| `CORREDOR_M` | 500 m | Solo se clasifica cerca del cauce de Las Lajas |
| `MANCHA_MIN` | 5 píxeles de 10 m | Manchas más chicas son ruido |
| `CONEXION_M` | 100 m | Una mancha cuenta solo si llega a esta distancia del cauce |

Los tres umbrales de NDVI son los iniciales de `docs/tareas/03_sentinel2.md`. En
`histogramas.png` la vegetación del corredor forma un pico cerca de 0.85 y el cauce
desnudo otro cerca de 0.05, así que 0.2 y 0.4 caen en el valle entre los dos. El
ΔNDVI de p1 es casi todo negativo (de marzo, época seca, a julio, lluvias, la
vegetación reverdece), así que en p1 muy pocos píxeles pasan de 0.25; en p2 el ΔNDVI
está centrado en 0 con una cola hacia valores positivos.
Clases de nubes y sombras excluidas (SCL): 0, 2, 3, 8, 9 y 10.

## Cómo se llegó al corredor final (proceso iterativo)

| Iteración | Cambio | Clase 2 en p2 | Qué se vio |
|---|---|---|---|
| 1 | Corredor de 500 m a lo largo de todo el cauce (38.6 km) | 3.05 km² | Parcelas rectangulares rojas en la parte baja: caña cosechada, no lodo |
| 2 | Las manchas tienen que tocar el cauce (≤ 100 m) | 2.11 km² | Las parcelas pegadas a la barranca siguen conectadas a través de la franja desnuda (clase 1) |
| 3 | Las manchas de clase 2 se revisan solas | 1.96 km² | Mejora poco: casi toda la clase 2 está entre los km 20 y 36 |
| 4 | **Corredor solo hasta la confluencia con el Guacalate (km 7.44)** | 0.01 km² | Pasando el km 7.4 el cauce es el río Guacalate (124 km² de cuenca): sus cambios vienen de sus propias crecidas y de la caña, no de los lahares de Las Lajas |

La iteración 4 cambió también la forma de validar: ver la sección siguiente.

## Resultado final (corredor de Las Lajas, km 0 a 7.44)

| Periodo | Fechas | Clase 2 | Clase 1 | Clase 0 | Sin dato |
|---|---|---|---|---|---|
| p1 (calibración) | 2019-03-26 → 2019-07-04 | 0.00 km² | 1.04 km² | 5.09 km² | 13 % |
| p2 (prueba) | 2019-07-04 → 2019-12-11 | 0.01 km² | 0.99 km² | 5.14 km² | 13 % |

**Hallazgo principal:** en Las Lajas casi no hay "cambio seguro" en 2019. Es la trampa
que se anticipaba: el flujo piroclástico de 2018 ya había pelado la barranca y los
lahares de 2019 corren por un cauce sin vegetación que perder. Por eso:

- La versión **estricta** no tiene casi celdas positivas y no sirve para calibrar.
- La versión **amplia** (clases 1 y 2) es el cauce desnudo: dice por dónde **puede**
  pasar el lodo, no hasta dónde llegó cada lahar.
- La calibración usa la versión amplia penalizando lo que se sale del corredor
  (ver `src/modelo/calibrar.py`), y la validación se complementa con el catálogo de
  boletines y el mapa del INSIVUMEH.

## Revisión a ojo

Las máscaras de 30 m superpuestas a la imagen RGB (`observado_p1.png`,
`observado_p2.png`) siguen la banda gris de la barranca. Queda pendiente la revisión de
5–10 puntos al azar en Google Earth Pro (imágenes históricas de 2019).
