"""Genera informe.pdf a partir de informe.md.

pandoc (incluido en el paquete pypandoc_binary) convierte el Markdown a un HTML
autocontenido con las figuras y las fórmulas en MathML, y Microsoft Edge en modo
headless lo imprime a PDF. Así no hace falta instalar LaTeX.

Uso:
    uv pip install pypandoc_binary
    python docs/informe/generar_pdf.py
"""

import subprocess
from pathlib import Path

import pypandoc

AQUI = Path(__file__).resolve().parent
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45;
       max-width: 17cm; margin: 0 auto; color: #222; }
h1 { font-size: 15pt; border-bottom: 1px solid #999; margin-top: 1.4em; }
h2 { font-size: 12.5pt; margin-top: 1.1em; }
header h1.title { font-size: 19pt; border: none; text-align: center; }
header p.subtitle, header p.author, header p.date { text-align: center; margin: 0.2em; }
table { border-collapse: collapse; margin: 0.6em 0; font-size: 9pt; }
th, td { border: 1px solid #bbb; padding: 3px 6px; vertical-align: top; }
th { background: #eee; }
code { font-size: 9pt; background: #f4f4f4; padding: 0 2px; }
figure { text-align: center; margin: 0.8em 0; page-break-inside: avoid; }
figure img { max-width: 100%; }
figcaption { font-size: 9pt; color: #555; }
@page { size: A4; margin: 2cm 1.8cm; }
"""


def main():
    css = AQUI / "estilo.css"
    css.write_text(CSS, encoding="utf-8")
    html = AQUI / "informe.html"
    pypandoc.convert_file(
        str(AQUI / "informe.md"), "html5", outputfile=str(html),
        extra_args=["--standalone", "--embed-resources", "--mathml",
                    f"--css={css}", f"--resource-path={AQUI}"],
    )
    pdf = AQUI / "informe.pdf"
    subprocess.run([str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.as_uri()], check=True)
    html.unlink()
    css.unlink()
    print(f"Guardado {pdf}")


if __name__ == "__main__":
    main()
