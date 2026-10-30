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

