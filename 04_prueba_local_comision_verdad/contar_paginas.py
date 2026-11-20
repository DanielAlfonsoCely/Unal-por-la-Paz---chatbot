"""
Cuenta las páginas de todos los PDF de una carpeta (y sus subcarpetas).

Uso (en la torre, una sola vez):  pip install pypdf
Luego:  python contar_paginas.py "C:\\ruta\\a\\la\\carpeta\\de\\los\\libros"
"""
import sys
from pathlib import Path

from pypdf import PdfReader

carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
total, archivos = 0, 0
for pdf in sorted(carpeta.rglob("*.pdf")):
    try:
        n = len(PdfReader(pdf).pages)
        total += n
        archivos += 1
        print(f"{n:>6}  {pdf.name}")
    except Exception as e:
        print(f"  ERROR {pdf.name}: {e}")
print(f"\n{archivos} PDF, {total} páginas en total")