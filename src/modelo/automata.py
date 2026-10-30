"""Autómata celular de lahares sobre el DEM.

Algoritmo de minimización de diferencias (Di Gregorio & Serra, 1999),
simplificado. Cada celda tiene terreno `z` (fijo) y espesor de lodo `h`.
En cada paso, cada celda con lodo reparte parte de él entre sus 8 vecinas
cuya superficie libre (z + h) está más baja, en proporción a la diferencia
de altura dividida entre la distancia.

Versiones:
    v1: todo el lodo puede moverse; se comporta como agua y solo se detiene
        en depresiones o al salir de la zona.
    v2: el lodo tiene resistencia. Una celda solo cede el lodo que pasa de un
        espesor crítico h_crit = max(h_min, tau_y / (ρ g sen θ)), con θ la
        pendiente de la superficie libre hacia el vecino más bajo. En pendiente
        fuerte h_crit es pequeño (fluye); en terreno plano es enorme (se detiene).
        Con tau_y = 0 queda la versión simple (espesor mínimo fijo h_min).

El paso se compila con Numba; solo se recorre el rectángulo donde ya hay
lodo (más un borde de una celda), que crece conforme avanza el flujo.
"""

from dataclasses import dataclass

import numpy as np
from numba import njit

VERSIONES = ("v1", "v2")
G = 9.81  # m/s²
UMBRAL_ALCANCE = 0.1  # m; una celda cuenta como "alcanzada" con más de 10 cm de lodo

# Vecindad de Moore: desplazamientos (fila, col).
_DF = np.array([-1, -1, -1, 0, 0, 1, 1, 1], dtype=np.int64)
_DC = np.array([-1, 0, 1, -1, 1, -1, 0, 1], dtype=np.int64)
_DIAG = np.array([1, 0, 1, 0, 0, 1, 0, 1], dtype=np.bool_)


@dataclass
class Parametros:
    relajacion: float = 0.5     # fracción del exceso que se mueve por paso (0–1]
    h_min: float = 0.0          # m, espesor que se queda quieto (v2, versión simple)
    tau_y: float = 0.0          # Pa, resistencia del lodo (v2, versión física)
    densidad: float = 2000.0    # kg/m³ de la mezcla
    max_pasos: int = 20_000
    tol: float = 1e-4           # se detiene si se mueve menos de tol × volumen por paso
    pasos_fuente: int = 100     # pasos en que se suelta el volumen (1 = todo de golpe)


@dataclass
class Resultado:
    h_final: np.ndarray         # espesor final de lodo, m
    h_max: np.ndarray           # espesor máximo alcanzado en cada celda, m
    alcanzado: np.ndarray       # bool: h_max > UMBRAL_ALCANCE
    paso_llegada: np.ndarray    # primer paso con h > UMBRAL_ALCANCE (-1 si nunca)
    pasos: int                  # pasos hasta detenerse
    volumen_perdido: float      # m³ que salieron por el borde de la zona
    convergio: bool             # False si se llegó a max_pasos


@njit(cache=True)
def _paso(z, h, dh, r0, r1, c0, c1, relajacion, res, resistencia, h_min, tau_y, densidad):
    """Un paso síncrono sobre las filas r0..r1 y columnas c0..c1 (inclusive).

    Calcula todos los flujos con el estado actual (`h`), los acumula en `dh`
    y luego los aplica. Con `resistencia` (v2) solo se mueve el lodo por encima
    del espesor crítico. Devuelve (volumen movido, volumen que salió de la zona,
    y el rectángulo r0, r1, c0, c1 donde quedó lodo).
    """
    nf, nc = h.shape
    d_diag = res * np.sqrt(2.0)
    movido = 0.0
    perdido = 0.0

    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            hi = h[i, j]
            if hi <= 0.0:
                continue
            Hi = z[i, j] + hi

            # Pesos de cada vecino receptor y la superficie más baja.
            pesos = np.zeros(8)
            suma = 0.0
            H_min = Hi
            d_min = res
            for k in range(8):
                fi = i + _DF[k]
                fj = j + _DC[k]
                d = d_diag if _DIAG[k] else res
                if 0 <= fi < nf and 0 <= fj < nc:
                    Hj = z[fi, fj] + h[fi, fj]
                else:
                    # Fuera de la zona: borde absorbente al nivel del terreno de la celda.
                    Hj = z[i, j]
                if Hj < Hi:
                    pesos[k] = (Hi - Hj) / d
                    suma += pesos[k]
                    if Hj < H_min:
                        H_min = Hj
                        d_min = d
            if suma == 0.0:
                continue

            h_mov = hi
            if resistencia:
                h_crit = h_min
                if tau_y > 0.0:
                    tan_t = (Hi - H_min) / d_min
                    sen_t = tan_t / np.sqrt(1.0 + tan_t * tan_t)
                    h_crit = max(h_crit, tau_y / (densidad * G * sen_t))
                h_mov = hi - h_crit
                if h_mov <= 0.0:
                    continue

            # Nunca más de la mitad de la diferencia con el vecino más bajo,
            # para que no oscile.
            salida = relajacion * min(h_mov, 0.5 * (Hi - H_min))
            if salida <= 0.0:
                continue
            dh[i, j] -= salida
            movido += salida
            for k in range(8):
                if pesos[k] == 0.0:
                    continue
                parte = salida * pesos[k] / suma
                fi = i + _DF[k]
                fj = j + _DC[k]
                if 0 <= fi < nf and 0 <= fj < nc:
                    dh[fi, fj] += parte
                else:
                    perdido += parte

    # Aplicar los flujos y medir el nuevo rectángulo con lodo.
    nr0, nr1, nc0, nc1 = nf, -1, nc, -1
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if dh[i, j] != 0.0:
                h[i, j] += dh[i, j]
                dh[i, j] = 0.0
                if h[i, j] < 0.0:  # error de redondeo
                    h[i, j] = 0.0
            if h[i, j] > 0.0:
                nr0 = min(nr0, i)
                nr1 = max(nr1, i)
                nc0 = min(nc0, j)
                nc1 = max(nc1, j)

    area = res * res
    return movido * area, perdido * area, nr0, nr1, nc0, nc1


@njit(cache=True)
def _actualizar_registro(h, h_max, paso_llegada, paso, r0, r1, c0, c1, umbral):
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if h[i, j] > h_max[i, j]:
                h_max[i, j] = h[i, j]
            if paso_llegada[i, j] < 0 and h[i, j] > umbral:
                paso_llegada[i, j] = paso


def simular(dem, fuente, volumen_m3, params=None, version="v1", res=30.0):
    """Simula un lahar que nace en `fuente` (fila, col) con `volumen_m3` de lodo.

    Devuelve un `Resultado` con arreglos del mismo tamaño que `dem`.
    """
    if version not in VERSIONES:
        raise ValueError(f"version debe ser una de {VERSIONES}")
    params = params or Parametros()
    if not 0 < params.relajacion <= 1:
        raise ValueError("relajacion debe estar en (0, 1]")

    z = np.ascontiguousarray(dem, dtype=np.float64)
    nf, nc = z.shape
    fi, fj = fuente
    if not (0 <= fi < nf and 0 <= fj < nc):
        raise ValueError(f"fuente {fuente} fuera de la cuadrícula {z.shape}")

    area = res * res
    h = np.zeros_like(z)
    dh = np.zeros_like(z)
    h_max = np.zeros_like(z)
    paso_llegada = np.full(z.shape, -1, dtype=np.int32)

    # Rectángulo activo: donde hay lodo, más un borde de una celda.
    r0 = r1 = fi
    c0 = c1 = fj

    h_por_paso = volumen_m3 / params.pasos_fuente / area
    perdido = 0.0
    convergio = False
    paso = 0
    for paso in range(1, params.max_pasos + 1):
        if paso <= params.pasos_fuente:
            h[fi, fj] += h_por_paso
            r0, r1 = min(r0, fi), max(r1, fi)
            c0, c1 = min(c0, fj), max(c1, fj)

        # El lodo avanza como mucho una celda por paso: basta con agrandar
        # el rectángulo una celda por lado.
        a0, a1 = max(r0 - 1, 0), min(r1 + 1, nf - 1)
        b0, b1 = max(c0 - 1, 0), min(c1 + 1, nc - 1)
        movido, salio, r0, r1, c0, c1 = _paso(
            z, h, dh, a0, a1, b0, b1, params.relajacion, res,
            version == "v2", params.h_min, params.tau_y, params.densidad)
        perdido += salio
        _actualizar_registro(h, h_max, paso_llegada, paso, a0, a1, b0, b1, UMBRAL_ALCANCE)

        if paso < params.pasos_fuente:
            continue
        if r1 < 0 or movido < params.tol * volumen_m3:  # r1 < 0: todo el lodo salió
            convergio = True
            break

    return Resultado(
        h_final=h,
        h_max=h_max,
        alcanzado=h_max > UMBRAL_ALCANCE,
        paso_llegada=paso_llegada,
        pasos=paso,
        volumen_perdido=perdido,
        convergio=convergio,
    )
