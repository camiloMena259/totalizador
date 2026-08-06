"""
debug_extractor.py
Imprime el texto crudo que pdfplumber extrae de cada página, línea por
línea, y cómo quedaría separado por columnas (2+ espacios).

Uso:
    python debug_extractor.py ruta/al/extracto.pdf
"""

import sys
import re
import pdfplumber

_SEP_COLUMNAS = re.compile(r'\s{2,}')


def main(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            print(f"\n===== PÁGINA {i} =====")
            text = page.extract_text() or ""
            for linea in text.split("\n"):
                columnas = _SEP_COLUMNAS.split(linea.strip())
                print(f"[{len(columnas)} cols] {columnas}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python debug_extractor.py ruta/al/extracto.pdf")
        sys.exit(1)
    main(sys.argv[1])