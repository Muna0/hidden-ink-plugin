"""Build small PDFs for tests, demos, and the benchmark."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

BODY = [
    "MASTER SERVICES AGREEMENT",
    "1. Services. Provider shall perform the services described in each Statement of Work.",
    "2. Fees. Client shall pay all undisputed invoices within thirty (30) days of receipt.",
    "3. Indemnification. Each party shall indemnify the other against third-party claims.",
]


def body(c: Canvas) -> None:
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 11)
    for i, line in enumerate(BODY):
        c.drawString(72, 720 - i * 18, line)


def scan_image() -> ImageReader:
    img = Image.new("RGB", (1224, 1584), "white")
    draw = ImageDraw.Draw(img)
    for i in range(30):
        draw.rectangle([144, 200 + i * 40, 1080, 214 + i * 40], fill=(40, 40, 40))
    return ImageReader(img)


def build_pdf(path: Path, draw: Callable[[Canvas], None], *, subject: str | None = None) -> Path:
    c = Canvas(str(path), pagesize=LETTER)
    if subject:
        c.setSubject(subject)
    draw(c)
    c.showPage()
    c.save()
    return path
