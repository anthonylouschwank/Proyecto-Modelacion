# P3 – Sentinel-2: mapa de lo observado

**Responsable:** [nombre]
**Carpeta:** `src/sentinel/` (archivos nuevos), `results/sentinel/`
**Lean primero:** [00_general.md](00_general.md) (contratos y cronograma)

## Objetivo

Producir la **"respuesta correcta"**: un mapa de dónde pasó realmente el lodo en Las
Lajas en cada periodo de 2019, a partir de imágenes satelitales. Con ese mapa P4 mide si
el modelo le atina, y P1 lo usa para calibrar.

Lo que ya existe (lean `data/README.md`, sección 3):
- `src/sentinel/buscar.py`: busca fechas con poca nube **sobre nuestra zona**.
- `src/sentinel/descargar.py`: baja el recorte de una fecha (rojo, NIR, máscara de nubes
  y una vista previa RGB), ya en reflectancia y en UTM 15N a 10 m.
- Ya está bajada la del **2019-03-26**.

---

## 1. Bajar las otras fechas

```bash
python -m src.sentinel.descargar --fecha 2019-07-04
python -m src.sentinel.descargar --fecha 2019-12-11
python -m src.sentinel.descargar --fecha 2020-01-10   # respaldo de diciembre
```

| Periodo | Antes | Después |
|---|---|---|
| **p1** (calibración) | 2019-03-26 | 2019-07-04 |
| **p2** (prueba) | 2019-07-04 | 2019-12-11 |

Miren las vistas previas `s2_*_rgb.png` antes de procesar nada.

## 2. La trampa: la barranca ya estaba pelada

El flujo piroclástico y los lahares de **2018** ya arrasaron la vegetación del cauce de
Las Lajas. En 2019 muchos lahares pasan **por dentro de ese cauce ya desnudo**, y el
ΔNDVI no ve nada ahí porque no había vegetación que perder.

Por eso el mapa observado lleva **dos niveles de certeza**:

| Clase | Significado | Cómo se detecta |
|---|---|---|
| **2 – cambio seguro** | Había vegetación y ya no: el lodo llegó a un lugar nuevo | `NDVI_antes ≥ 0.4` y `ΔNDVI = NDVI_antes − NDVI_después ≥ 0.25` |
| **1 – posible** | Desnudo al final, pero ya lo estaba al inicio: pudo pasar lodo o no | `NDVI_después < 0.2` y no es clase 2 |
| **0 – no** | Vegetación al final | resto |
| **255 – sin dato** | Nube, sombra de nube o sombra topográfica en cualquiera de las dos fechas | SCL ∈ {0, 2, 3, 8, 9, 10} |

Los umbrales (0.4, 0.25, 0.2) son **iniciales**: ajústenlos viendo los histogramas y las
imágenes. P4 calcula las métricas de dos formas:
- **Estricta:** observado = clase 2.
- **Amplia:** observado = clase 1 o 2.

La realidad está entre las dos. Reportar ese rango es más honesto que un solo número.

> **Una pista extra para la clase 1:** las zonas desnudas en marzo que **reverdecen**
> en julio probablemente NO recibieron lodo (la vegetación volvió). Pueden usar eso para
> afinar.

## 3. Otras trampas

| Problema | Por qué | Qué hacer |
|---|---|---|
| **Caña de azúcar** | La zafra (nov–abr) deja campos desnudos: parecen lodo | Trabajar **solo dentro del corredor** de la barranca (sección 4) |
| **Cambio de estación** | En marzo (seco) todo está menos verde que en julio | Por eso se usan umbrales sobre ΔNDVI y no solo NDVI; revisen los histogramas por fecha |
| **Ceniza en el cono** | Cerca del cráter todo es gris todo el año | Excluir lo que esté **arriba de la fuente** (el modelo empieza ahí) |
| **Sombras en el cono** | El volcán es empinado: la SCL marca "zona oscura" (clase 2) | Ya va como sin dato (255) |

## 4. El corredor

Para no confundir campos de caña con lodo, **solo se clasifica dentro de un corredor**
alrededor de la barranca:

- **Corredor definitivo:** celdas a ≤ 500 m de `data/processed/lajas_cauce.tif`
  (lo entrega P2 el vie 30), y por debajo de la fuente.
- **Mientras tanto:** dibujen un polígono a mano alrededor de los depósitos grises de Las
  Lajas en la imagen de marzo (QGIS o coordenadas a mano), o usen la zona coloreada del
  mapa del INSIVUMEH en esa barranca.

Fuera del corredor, la máscara vale 255 (sin dato).

## 5. Script y salidas

Script `src/sentinel/ndvi.py`, con `python -m src.sentinel.ndvi`:

1. Leer `s2_<fecha>_refl.tif` y `s2_<fecha>_scl.tif` de las dos fechas del periodo.
2. `NDVI = (NIR − Rojo) / (NIR + Rojo)` para cada fecha; `ΔNDVI = antes − después`.
3. Clasificar (sección 2), aplicar la máscara de nubes y el corredor.
4. Limpiar ruido: quitar manchas aisladas de pocos píxeles (`scipy.ndimage` o morfología).
5. **Pasar de 10 m a 30 m** (cuadrícula del DEM): para cada celda de 30 m, que tiene 3 × 3
   píxeles de 10 m, la clase es la mayoritaria; si hay más de la mitad sin dato, va 255.
   Ojo: el recorte de Sentinel-2 y el DEM cubren **la misma zona**, así que son
   exactamente 3840 × 3840 → 1280 × 1280, sin reproyectar.

### Salidas (contrato con P4 y P1)

| Archivo | Contenido |
|---|---|
| `data/processed/observado_lajas_2019_p1.tif` | uint8 (0 / 1 / 2 / 255), cuadrícula del DEM |
| `data/processed/observado_lajas_2019_p2.tif` | igual, para p2 |
| `results/sentinel/ndvi_<periodo>.png` | antes / después / ΔNDVI lado a lado |
| `results/sentinel/observado_<periodo>.png` | clases sobre la imagen RGB |
| `results/sentinel/umbrales.md` | umbrales usados y por qué (con histogramas) |

## 6. ⚠️ Regla de honestidad

**Congelen los umbrales antes del Hito 2 (dom 1)**, antes de ver los resultados del
modelo. Si los ajustan después para que el modelo "salga mejor", la validación pierde
todo su valor. Cualquier cambio posterior se documenta como tal.

## 7. Cómo saber que está bien

- La clase 2 aparece en **bordes nuevos** del cauce y en lugares donde la imagen RGB
  muestra gris nuevo; no en campos de caña.
- La máscara p1 de 30 m, superpuesta al RGB, "se ve bien" a ojo.
- Revisen 5 o 10 puntos al azar en Google Earth Pro (imágenes históricas de 2019) y
  anoten cuántos coinciden. Esa es la validación de su propio mapa y va en el documento.

---

## 8. Tu cronograma

| Día | Tarea |
|---|---|
| **Jue 29** | Bajar las fechas; NDVI de las 3; histogramas; corredor a mano |
| **Vie 30** | **🔗 Hito 1:** máscara p1 preliminar (corredor a mano) |
| **Sáb 31** | Corredor de P2; máscaras p1 y p2 limpias en 30 m; figuras; `umbrales.md` |
| **Dom 1** | **🔗 Hito 2:** umbrales congelados; apoyo a P1 y P4 en la calibración; revisión en Google Earth |
| **Lun 2** | Escribir la sección "Datos: Sentinel-2 y mapa observado" con sus limitaciones |
| **Mar 3** | Revisar el documento |

**Extra si da tiempo:** una imagen de antes de la erupción (mayo de 2018) para mostrar en
la introducción cómo quedó Las Lajas después del 3 de junio.

## 9. Dependencias

| Necesito | De | Mientras tanto |
|---|---|---|
| `lajas_cauce.tif` y `lajas_fuente.json` | P2 (vie 30) | Polígono a mano |

| Doy | A | Cuándo |
|---|---|---|
| `observado_lajas_2019_p1.tif` | P1 y P4 | preliminar vie 30, final sáb 31 |
| `observado_lajas_2019_p2.tif` | P4 | sáb 31 |

## 10. Limitaciones para documentar

- La imagen muestra la **temporada acumulada**, no lahares individuales.
- El cauce ya desnudo de 2018 esconde parte de los lahares (de ahí las clases 1 y 2).
- La resolución de 10 m no distingue depósitos delgados ni muy angostos.
- Los umbrales de NDVI son una elección; se reportan junto con su sensibilidad.
