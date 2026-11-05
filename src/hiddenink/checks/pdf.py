"""Turn PDF facts into findings."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ..language import instruction_like
from ..model import Finding, Location, Visibility
from ..readers.pdf import PageFacts, Span, read_pdf
from .unicode import check_unicode
from ..color import rgb_distance
from ..render import RENDER_SCALE, open_renderer

H, U = Visibility.HIDDEN, Visibility.UNCERTAIN
GPO_SLUG = re.compile(r"\bVerDate\b|\bJkt\s+\d+|\bPO\s+\d{5}\b|\bFrm\s+\d+|\bSfmt\s+\d+", re.I)
LONG_HIDDEN_VALUE = 200
SCAN_COVERAGE = 0.5
SCAN_MAX_VISIBLE_CHARS = 24


def _image_coverage(page: PageFacts) -> float:
    if not page.image_boxes or page.width <= 0 or page.height <= 0:
        return 0.0
    grid = np.zeros((100, 100), dtype=bool)
    for x0, y0, x1, y1 in page.image_boxes:
        c0, c1 = int(max(0, x0) / page.width * 100), int(min(page.width, x1) / page.width * 100)
        r0, r1 = int(max(0, y0) / page.height * 100), int(min(page.height, y1) / page.height * 100)
        grid[r0:r1, c0:c1] = True
    return float(grid.mean())


def _inside_any(span: Span, boxes) -> bool:
    cx, cy = (span.bbox[0] + span.bbox[2]) / 2, (span.bbox[1] + span.bbox[3]) / 2
    return any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in boxes)


def _off_page(span: Span, page: PageFacts) -> bool:
    x0, y0, x1, y1 = span.bbox
    return x1 <= 0 or y1 <= 0 or x0 >= page.width or y0 >= page.height


def structural_verdict(span: Span, page: PageFacts, scan_like: bool) -> tuple[str, Visibility, str, bool] | None:
    """Return (technique, visibility, explanation, benign) or None when no structural problem."""
    if span.render_mode in (3, 7):
        if scan_like and _inside_any(span, page.image_boxes):
            return ("pdf.ocr_layer", U, "Invisible text over a scanned image, which is a normal OCR text layer.", True)
        return ("pdf.invisible_render_mode", H, "This text is set to an invisible drawing mode, so it never shows.", False)
    if _off_page(span, page):
        return ("pdf.off_page", H, "This text is positioned outside the visible page.", False)
    if span.size < 2:
        return ("pdf.tiny_font", H, f"Font size is {span.size:.1f}pt, too small for a person to read.", False)
    return None


def _finding(span: Span, verdict) -> Finding:
    technique, visibility, why, benign = verdict
    if not benign and GPO_SLUG.search(span.text):
        technique, visibility, why, benign = ("pdf.gpo_stamp", U,
                                              "A printing-office tracking stamp, normally invisible and harmless.", True)
    return Finding(technique, visibility, Location(page=span.page, bbox=span.bbox), span.text, why, benign=benign)


INVISIBLE_SPREAD = 24  # luminance spread (0-255) below which nothing is drawn
COLOR_MATCH = 40  # RGB distance below which text color equals its background


def render_verdict(span: Span, img: np.ndarray) -> tuple[str, Visibility, str, bool] | None:
    h, w, _ = img.shape
    x0, y0, x1, y1 = (int(round(v * RENDER_SCALE)) for v in span.bbox)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    region = img[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    lum = region @ np.array([0.299, 0.587, 0.114])
    spread = float(np.percentile(lum, 95) - np.percentile(lum, 5))
    background = tuple(float(v) for v in np.median(region, axis=0))
    matches_bg = span.rgb is not None and rgb_distance(span.rgb, background) < COLOR_MATCH
    if spread < INVISIBLE_SPREAD and matches_bg:
        return ("pdf.low_contrast", H, "The text color matches its background, so nothing shows on the page.", False)
    if spread < INVISIBLE_SPREAD:
        dark = sum(background) / 3 < 60
        why = ("Something is drawn over this text, hiding it."
               + (" A dark box over text can be a failed redaction: the text is still in the file." if dark else ""))
        return ("pdf.covered_text", H, why, False)
    if matches_bg:
        return ("pdf.low_contrast", U, "The text color matches its background in this area; it may not be visible.", False)
    return None


def scan_pdf(path: Path) -> tuple[list[Finding], str]:
    facts = read_pdf(path)
    findings: list[Finding] = []
    lines: list[str] = []
    renderer = open_renderer(path)
    try:
        for page in facts.pages:
            visible_chars = sum(len(s.text.strip()) for s in page.spans if s.render_mode not in (3, 7))
            scan_like = _image_coverage(page) >= SCAN_COVERAGE and visible_chars < SCAN_MAX_VISIBLE_CHARS
            unresolved: list[Span] = []
            for span in page.spans:
                verdict = structural_verdict(span, page, scan_like)
                if verdict is not None:
                    findings.append(_finding(span, verdict))
                else:
                    unresolved.append(span)
                findings.extend(check_unicode(span.text, Location(page=span.page, bbox=span.bbox)))
            visible_spans: list[Span] = []
            if unresolved:
                img = renderer.page_image(page.number)
                for span in unresolved:
                    verdict = render_verdict(span, img)
                    if verdict is None:
                        visible_spans.append(span)
                    else:
                        findings.append(_finding(span, verdict))
                del img
            lines.append(" ".join(s.text.strip() for s in visible_spans))
            for text in page.annotations:
                findings.append(Finding("pdf.annotation", U, Location(page=page.number), text,
                                        "Annotation text is stored on the page, and many AI tools read it.", benign=True))
    finally:
        renderer.close()
    for key, value in facts.metadata:
        hit, _ = instruction_like(value)
        if hit or len(value) > LONG_HIDDEN_VALUE:
            findings.append(Finding("metadata.field", U, Location(path=key), value,
                                    f"Document property '{key}' is not shown on the page, but AI tools may read it."))
    return findings, "\n".join(line for line in lines if line)
