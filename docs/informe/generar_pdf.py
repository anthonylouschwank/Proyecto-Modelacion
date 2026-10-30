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

# Mismo estilo que los informes de laboratorio del curso: Times, texto
# justificado, portada propia y tablas con encabezado negro.
CSS = """
body { font-family: "Times New Roman", Times, serif; font-size: 11.5pt; line-height: 1.4;
       max-width: 17cm; margin: 0 auto; color: #000; text-align: justify; }
h1 { font-size: 18pt; font-weight: bold; margin: 1.2em 0 0.4em; text-align: left; }
h2 { font-size: 14pt; font-weight: bold; margin: 1em 0 0.3em; text-align: left; }
.portada { text-align: center; page-break-after: always; padding-top: 0.6cm; }
.portada p { margin: 0.35em 0; }
.portada .uvg { font-size: 15pt; margin-bottom: 1.2em; }
.portada .logo { width: 4.2cm; margin: 0.9cm 0 0.8cm; }
.portada .titulo { font-size: 17pt; margin-top: 0.5em; }
.portada .subtitulo { font-size: 12.5pt; }
.portada .integrantes { margin: 1cm 0 0.7cm; }
.portada .repo { font-size: 10.5pt; }
.portada .fecha { margin-top: 0.8cm; }
table { border-collapse: collapse; margin: 0.7em auto; font-size: 9.5pt; text-align: center; }
th { background: #000; color: #fff; font-weight: bold; padding: 4px 8px; }
td { padding: 4px 8px; border-bottom: 1px solid #ccc; vertical-align: top; }
tr:nth-child(even) td { background: #f0f0f0; }
code { font-family: Consolas, monospace; font-size: 9.5pt; }
figure { text-align: center; margin: 0.8em 0; page-break-inside: avoid; }
figure img { max-width: 100%; }
figcaption { font-size: 10pt; font-style: italic; }
a { color: #000; }
@page { size: letter; margin: 2.2cm 2cm; }
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
