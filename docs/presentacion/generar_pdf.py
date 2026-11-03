"""Genera presentacion.pdf a partir de presentacion.html con Microsoft Edge headless.

Uso:
    python docs/presentacion/generar_pdf.py
"""

import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def main():
    html = AQUI / "presentacion.html"
    pdf = AQUI / "presentacion.pdf"
    subprocess.run([str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.as_uri()], check=True)
    print(f"Guardado {pdf}")


if __name__ == "__main__":
    main()
