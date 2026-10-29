"""Rangos de los parámetros del Monte Carlo y de dónde salen.

Todos se sortean con distribución uniforme (no hay datos para algo mejor).
Si cambian un rango, actualicen también su justificación aquí abajo.

------------------------------------------------------------------------------
C – coeficiente de escurrimiento: 0.3 – 0.7
------------------------------------------------------------------------------
Fracción de la lluvia que baja por la barranca en vez de infiltrarse.

- La ceniza fina recién caída forma una costra en la superficie (surface
  sealing) que baja la infiltración y produce escurrimiento superficial de tipo
  Horton. En experimentos con lluvia simulada sobre tefra de Kelud y Chaitén, una
  capa superficial fina produjo hasta 1500 % más escurrimiento que una
  gruesa, y la lluvia previa (suelo ya húmedo) lo aumenta todavía más:
    Jones, R., Thomas, R. E., Peakall, J. y Manville, V. (2017). Rainfall-runoff
    properties of tephra: simulated effects of grain-size and antecedent
    rainfall. Geomorphology, 282, 39–51. doi:10.1016/j.geomorph.2016.12.023
- Revisión general de cómo la tefra reduce la infiltración y aumenta el
  escurrimiento y la erosión en cuencas volcánicas:
    Pierson, T. C. y Major, J. J. (2014). Hydrogeomorphic effects of explosive
    volcanic eruptions on drainage basins. Annual Review of Earth and Planetary
    Sciences, 42, 469–507. doi:10.1146/annurev-earth-060313-054913
- Fuego hace erupciones casi todos los días, así que la parte alta de Las Lajas
  siempre tiene ceniza fresca → C más alto que en un suelo con vegetación.

OJO: no encontramos un valor de C medido en Fuego. El rango es una suposición
apoyada en lo cualitativo de arriba: el piso (0.3) es una cuenca con algo de
infiltración y el techo (0.7) es una superficie casi sellada. Es el parámetro
más débil; si alguien encuentra un valor medido, cámbienlo.

------------------------------------------------------------------------------
Cs – concentración de sedimento en volumen: 0.3 – 0.6
------------------------------------------------------------------------------
Fracción del volumen del lahar que es sólido. V_lahar = V_agua / (1 − Cs).

- Clasificación reológica de flujos de agua y sedimento (la clásica):
    Pierson, T. C. y Costa, J. E. (1987). A rheologic classification of
    subaerial sediment-water flows. Reviews in Engineering Geology, 7, 1–12.
    doi:10.1130/REG7-p1
- Flujo hiperconcentrado: de ~5 % a ~60 % de sedimento en volumen según el
  autor; flujo de detritos: arriba de ~60 %:
    Pierson, T. C. (2005). Hyperconcentrated flow – transitional process between
    water flow and debris flow. En Jakob, M. y Hungr, O. (eds.), Debris-flow
    Hazards and Related Phenomena, pp. 159–202. Springer.
    Vallance, J. W. e Iverson, R. M. (2015). Lahars and their deposits. En
    Sigurdsson, H. et al. (eds.), The Encyclopedia of Volcanoes, 2.ª ed.,
    pp. 649–664. Academic Press.
- El rango 0.3–0.6 cubre los flujos hiperconcentrados y llega al límite de los
  flujos de detritos, que son los lahares que se describen en Las Lajas. Los
  límites varían entre autores porque la concentración sola no basta para
  separar los tipos de flujo (también importan la granulometría y la velocidad).
- Ojo con la sensibilidad: con Cs = 0.6 el volumen es 2.5 × el agua; con 0.3,
  1.4 ×. Si se sube el techo a 0.7–0.8 (flujo de detritos denso) el volumen
  crece rápido (3.3 × y 5 ×).

------------------------------------------------------------------------------
factor_lluvia – corrección de la lluvia de Open-Meteo: 1.0 – 1.5
------------------------------------------------------------------------------
Multiplica la lluvia de la tormenta antes de calcular el volumen.

- La lluvia sale de un modelo meteorológico (ECMWF IFS, celda de ~9 km), no de
  un pluviómetro. La celda promedia todo el cono, y las tormentas convectivas
  de la tarde son más pequeñas que la celda.
- Comparación propia (data/README.md, sección 2): en el cráter, jun–oct 2019,
  ERA5 (~25 km) da 33 % menos lluvia que IFS (~9 km) y suaviza los picos
  diarios (58 vs 87 mm). Que la lluvia crezca al refinar la celda sugiere que
  IFS también se queda corto respecto al punto.
- La lluvia de una celda es un promedio de área: la lluvia en un punto (lo que
  mediría un pluviómetro) tiene picos más altos, y la diferencia crece en
  tormentas convectivas y en relieve fuerte. ECMWF lo documenta y por eso
  posprocesa ERA5 (ecPoint) para estimar la lluvia puntual y sus extremos:
    "Bridging the scale gap: enhancing point-scale rainfall estimates by
    post-processing ERA5", memorándum técnico de ECMWF (2025),
    https://www.ecmwf.int/bibcite/reference/81693
    ECMWF Newsletter n.º 176 (ERA5-ecPoint, caso de la tormenta Alex, 2020),
    https://www.ecmwf.int/node/28827
  Nuestro dato es IFS, no ERA5, pero el efecto de promediar en la celda es el
  mismo, solo que menor (9 km en vez de 25 km).
- Por eso el factor es >= 1 (nunca reducimos la lluvia). El techo de 1.5 es
  una suposición: no tenemos pluviómetro en Fuego para medir el sesgo. Si P4
  consigue datos de una estación del INSIVUMEH, se puede calibrar.

------------------------------------------------------------------------------
relajacion y h_min – parámetros del autómata (P1): ± 30 % de lo calibrado
------------------------------------------------------------------------------
- No son propiedades medibles del lodo sino parámetros del modelo, así que no
  hay literatura que dé su rango: el ± 30 % representa la incertidumbre de la
  calibración con el periodo p1 (2019-03-26 → 2019-07-04).
- Mejor opción cuando P1 calibre: en vez del ± 30 %, usar el rango de valores
  que dieron un ajuste aceptable (p. ej., Jaccard dentro del 10 % del mejor).
- Por ahora: relajacion 0.5 ± 30 % = 0.35–0.65 (valor por defecto de v1), y
  h_min = 0 (v1 no lo usa). Actualizar con los valores de v2/v3.

------------------------------------------------------------------------------
También es una suposición (en src/inputs/volumen.py)
------------------------------------------------------------------------------
- umbral_mm = 20 mm por tormenta: no encontramos un umbral publicado para
  Fuego. La tesis de Buondonno hace un análisis estadístico de la lluvia que
  dispara lahares en Fuego (2017); es el primer lugar donde buscar un número:
    Buondonno, C. (2020). Rain generated lahars prior to the 2018 catastrophic
    eruption of Fuego volcano, Guatemala. Tesis de maestría, Michigan
    Technological University. doi:10.37099/mtu.dc.etdr/1150
  Compárenlo también con los días con lahar del catálogo (P4).
"""

RANGOS = {
    "C": (0.3, 0.7),
    "Cs": (0.3, 0.6),
    "factor_lluvia": (1.0, 1.5),
    "relajacion": (0.35, 0.65),
    "h_min": (0.0, 0.0),
}
