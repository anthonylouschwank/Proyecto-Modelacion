"""Descarga los mapas de amenaza de lahares del Volcán de Fuego (INSIVUMEH, 2018).

Son GeoTIFF georreferenciados en UTM 15N (~5.5 m/píxel), pero son la IMAGEN
del mapa (RGB), no zonas clasificadas. Para usarlos en la validación hay que
extraer las zonas de amenaza por color (pendiente) o compararlos a ojo.

Uso:
    python -m src.validacion.mapas_insivumeh

Salida: data/raw/insivumeh/
"""

import requests

from src.config import RAW

BASE = "https://insivumeh.gob.gt/wp-content/uploads/2026/05/"
MAPAS = {
    # Escenario A: lluvias moderadas. El TIF y el PDF daban 404 al 2026-10-27 (el JPG sí existe).
    "fuego_lahares_escenario_A.tif": BASE + "Fuego_crisis_lahares_scaled_A.tif",
    "fuego_lahares_escenario_A.pdf": BASE + "Fuego_crisis_lahares_escenario_A.pdf",
    # Escenario B: lluvias muy intensas (~58 MB).
    "fuego_lahares_escenario_B.tif": BASE + (
        "MAPA-PRELIMINAR-DE-AMENAZA-DE-LAHARES-CRISIS-ERUPTIVA-DEL-VOLCAN-DE-FUEGO-"
        "JUNIO-2018-ESCENARIO-B-LLUVIAS-MUY-INTENSAS.tif"
    ),
}
SALIDA_DIR = RAW / "insivumeh"


def descargar(nombre, url):
    destino = SALIDA_DIR / nombre
    if destino.exists():
        print(f"  ya existe {destino.name}")
        return
    with requests.get(url, stream=True, timeout=120) as r:
        if r.status_code == 404:
            print(f"  NO DISPONIBLE (404): {nombre}")
            return
        r.raise_for_status()
        tmp = destino.with_suffix(destino.suffix + ".part")
        with open(tmp, "wb") as f:
            for bloque in r.iter_content(1 << 20):
                f.write(bloque)
        tmp.rename(destino)
    print(f"  guardado {destino.name} ({destino.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    for nombre, url in MAPAS.items():
        descargar(nombre, url)
