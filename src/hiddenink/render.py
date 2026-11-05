"""Render PDF pages to RGB arrays with pdfium."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

RENDER_SCALE = 2.0


class PageRenderer:
    def __init__(self, path: Path):
        self._doc = pdfium.PdfDocument(str(path))

    def page_image(self, number: int) -> np.ndarray:
        page = self._doc[number - 1]
        try:
            bitmap = page.render(scale=RENDER_SCALE)
            return np.asarray(bitmap.to_pil().convert("RGB"))
        finally:
            page.close()

    def close(self) -> None:
        self._doc.close()


def open_renderer(path: Path) -> PageRenderer:
    return PageRenderer(path)
