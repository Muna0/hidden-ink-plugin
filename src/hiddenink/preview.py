"""Page images and finding positions for the web viewer."""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from .model import ScanResult
from .readers.docx import read_docx

PREVIEW_SCALE = 1.5
MAX_PREVIEW_PAGES = 50


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _fraction_box(bbox, width: float, height: float) -> tuple[list[float] | None, bool]:
    """Turn a box in points into page fractions, clamped to the page. None if it is fully off the page."""
    x0, y0, x1, y1 = bbox
    fx0, fx1 = sorted((x0 / width, x1 / width))
    fy0, fy1 = sorted((y0 / height, y1 / height))
    if fx1 < 0 or fx0 > 1 or fy1 < 0 or fy0 > 1:
        return None, True
    clipped = fx0 < 0 or fy0 < 0 or fx1 > 1 or fy1 > 1
    # zero-size boxes (font size 0) are kept; the viewer gives every mark a minimum size
    return [_clamp(fx0), _clamp(fy0), _clamp(fx1), _clamp(fy1)], clipped


def pdf_preview(src: Path, result: ScanResult, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages, sizes = [], {}
    pdf = pdfium.PdfDocument(str(src))
    try:
        total = len(pdf)
        for number in range(1, min(total, MAX_PREVIEW_PAGES) + 1):
            page = pdf[number - 1]
            try:
                left, bottom, right, top = page.get_cropbox()
                width, height = right - left, top - bottom
                page.set_rotation(0)  # engine boxes are in unrotated crop-box coordinates
                image = page.render(scale=PREVIEW_SCALE).to_pil().convert("RGB")
                image.save(out_dir / f"page-{number}.png", optimize=True)
            finally:
                page.close()
            sizes[number] = (width, height)
            pages.append({"number": number, "width": width, "height": height})
    finally:
        pdf.close()
    marks = []
    for index, finding in enumerate(result.findings):
        loc = finding.location
        if loc.page in sizes and loc.bbox is not None:
            box, clipped = _fraction_box(loc.bbox, *sizes[loc.page])
            if box is not None:
                marks.append({"finding": index, "page": loc.page, "box": box, "clipped": clipped})
    return {"kind": "pages", "page_count": total, "pages": pages, "marks": marks}


PART_LABELS = (
    ("word/document.xml", "Body"),
    ("word/header", "Header"),
    ("word/footer", "Footer"),
    ("word/footnotes.xml", "Footnotes"),
    ("word/endnotes.xml", "Endnotes"),
    ("word/comments.xml", "Comments"),
    ("word/glossary/document.xml", "Building blocks"),
)


def _part_label(part: str) -> str:
    return next((label for prefix, label in PART_LABELS if part.startswith(prefix)), part)


def docx_preview(src: Path, result: ScanResult) -> dict:
    facts = read_docx(src)
    owner: dict[tuple[str, str], int] = {}
    for index, finding in enumerate(result.findings):
        for target in finding.targets:
            owner.setdefault((finding.location.part, target), index)
    blocks: list[dict] = []
    by_paragraph: dict[tuple[str, str], dict] = {}
    for r in facts.runs:
        finding = owner.get((r.part, r.path))
        if r.kind == "field" and finding is None:
            continue  # Word never shows field instructions; only flagged ones belong in the view
        key = (r.part, r.paragraph_path)
        block = by_paragraph.get(key)
        if block is None:
            block = {"part": r.part, "label": _part_label(r.part), "path": r.paragraph_path,
                     "finding": owner.get(key), "segments": []}
            by_paragraph[key] = block
            blocks.append(block)
        segments = block["segments"]
        if segments and segments[-1]["finding"] == finding:
            segments[-1]["text"] += r.text
        else:
            segments.append({"text": r.text, "finding": finding})
    order = {label: n for n, (_, label) in enumerate(PART_LABELS)}
    blocks.sort(key=lambda b: order.get(b["label"], len(order)))  # stable sort keeps document order
    return {"kind": "flow", "blocks": blocks}


def build_preview(src: Path, result: ScanResult, out_dir: Path) -> dict:
    src, out_dir = Path(src), Path(out_dir)
    if result.file_format == "pdf":
        return pdf_preview(src, result, out_dir)
    if result.file_format == "docx":
        return docx_preview(src, result)
    raise ValueError(f"No preview for {result.file_format}")
