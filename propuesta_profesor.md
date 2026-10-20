**Asunto:** Propuesta de proyecto – Modelación y Simulación (sección [X])

Buen día, [Nombre del profesor].

Espero que se encuentre muy bien.

Quisiera presentarle una propuesta de proyecto para el curso Modelación y Simulación (sección [X]). El proyecto es una "Simulación probabilística de lahares en el Volcán de Fuego mediante autómatas celulares y Monte Carlo".

La idea consiste en desarrollar un simulador que, a partir de la lluvia observada en un día dado, estime hasta dónde llegaría un lahar por una barranca del Volcán de Fuego (empezando por Las Lajas) y con qué probabilidad alcanzaría zonas como comunidades o la RN-14. Usaríamos el terreno real del volcán (Copernicus DEM, 30 m) y datos de lluvia de Open-Meteo.

Nosotros proponemos:

- Implementar un autómata celular sobre el modelo de elevación del volcán, desarrollado en iteraciones: v1 con flujo por pendiente, v2 con fricción y espesor mínimo de detención, v3 con la lluvia como entrada.
- Convertir la lluvia en volumen de lodo y aplicar Monte Carlo sobre los parámetros inciertos para obtener mapas de probabilidad de alcance.
- Validar el modelo contra eventos reales: áreas afectadas obtenidas de imágenes Sentinel-2, boletines del INSIVUMEH y datos de estudios publicados, separando eventos de calibración y de prueba.
- Medir el desempeño con el índice de Jaccard, el error de alcance y el acierto en puntos clave, y compararlo con el método estándar LAHARZ del USGS.
- Documentar el proceso iterativo, los resultados y las limitaciones del modelo.

¿Considera que este alcance es adecuado para el nivel del curso? Me gustaría conocer si recomienda algún ajuste o si podría aprobar la propuesta para reservar el tema.

Muchas gracias de antemano.

Saludos cordiales,
[Nombre], [Carné]
Integrantes: [Nombre 1], [Nombre 2], [Nombre 3], [Nombre 4]
