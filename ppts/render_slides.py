"""Rasteriza un PDF de diapositivas a JPEG para usarlos en present.html.

Uso:
    python render_slides.py
    python render_slides.py "otro.pdf" --scale 2 --quality 88

Requiere: pip install pymupdf
"""

from __future__ import annotations

import argparse
import glob
import os

import pymupdf

DEFAULT_PDF = "Green and White Clean Typographic Agriculture Presentation.pdf"
OUTPUT_DIRECTORY = "slides"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", default=DEFAULT_PDF)
    parser.add_argument("--scale", type=float, default=2.0, help="2.0 => 2880x1620 en 16:9")
    parser.add_argument("--quality", type=int, default=88)
    parser.add_argument("--output", default=OUTPUT_DIRECTORY)
    arguments = parser.parse_args()

    os.makedirs(arguments.output, exist_ok=True)
    for stale in glob.glob(os.path.join(arguments.output, "slide-*.jpg")):
        os.remove(stale)

    document = pymupdf.open(arguments.pdf)
    matrix = pymupdf.Matrix(arguments.scale, arguments.scale)
    for number, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        path = os.path.join(arguments.output, f"slide-{number:02d}.jpg")
        pixmap.pil_save(path, format="JPEG", quality=arguments.quality, optimize=True, progressive=True)
        print(f"{path}  {pixmap.width}x{pixmap.height}")

    print(f"\n{document.page_count} paginas listas en {arguments.output}/")
    print("Si cambio la cantidad de paginas, actualiza la lista SLIDES en present.html.")


if __name__ == "__main__":
    main()
