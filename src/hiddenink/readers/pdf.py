"""Read a PDF into text spans with color, size, position, and render mode."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTChar, LTContainer, LTImage, LTTextLine
from pdfminer.pdfdocument import PDFDocument, PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser, PDFSyntaxError
from pdfminer.pdftypes import PDFStream, resolve1
from pdfminer.psparser import PSException
from pdfminer.utils import decode_text

from ..errors import ScanError

Box = tuple[float, float, float, float]


@dataclass
class Span:
    page: int
    text: str
    bbox: Box  # points, origin top-left of the crop box
    rgb: tuple[int, int, int] | None
    size: float
    render_mode: int


@dataclass
class PageFacts:
    number: int
    width: float
    height: float
    spans: list[Span] = field(default_factory=list)
    image_boxes: list[Box] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)


@dataclass
class PdfFacts:
    pages: list[PageFacts] = field(default_factory=list)
    metadata: list[tuple[str, str]] = field(default_factory=list)


class _Aggregator(PDFPageAggregator):
    """Records the text render mode on every character (pdfminer drops it)."""

    _render_mode = 0

    def render_string(self, textstate, seq, ncs, graphicstate):
        self._render_mode = textstate.render
        super().render_string(textstate, seq, ncs, graphicstate)

    def render_char(self, *args, **kwargs):
        advance = super().render_char(*args, **kwargs)
        self.cur_item._objs[-1].render_mode = self._render_mode
        return advance


def _rgb(ch: LTChar) -> tuple[int, int, int] | None:
    color = getattr(ch.graphicstate, "ncolor", None)
    if color is None:
        return (0, 0, 0)
    values = list(color) if isinstance(color, (list, tuple)) else [color]
    try:
        v = [float(x) for x in values]
    except (TypeError, ValueError):
        return None
    if len(v) == 1:
        g = round(v[0] * 255)
        return (g, g, g)
    if len(v) == 3:
        return tuple(round(x * 255) for x in v)  # type: ignore[return-value]
    if len(v) == 4:
        c, m, y, k = v
        return tuple(round(255 * (1 - x) * (1 - k)) for x in (c, m, y))  # type: ignore[return-value]
    return None


def _text(value) -> str:
    value = resolve1(value)
    if isinstance(value, bytes):
        return decode_text(value)
    return str(value) if value is not None else ""


def _walk(obj):
    if isinstance(obj, LTTextLine):
        yield "line", obj
    elif isinstance(obj, LTImage):
        yield "image", obj
    elif isinstance(obj, LTChar):
        yield "line", [obj]
    elif isinstance(obj, LTContainer):
        for child in obj:
            yield from _walk(child)


def _spans(chars, page_no: int, to_top) -> list[Span]:
    spans: list[Span] = []
    cur: dict | None = None
    for ch in chars:
        if not isinstance(ch, LTChar):
            if cur is not None:
                cur["text"] += ch.get_text()
            continue
        key = (_rgb(ch), round(ch.size, 1), getattr(ch, "render_mode", 0))
        if cur is not None and cur["key"] == key:
            cur["text"] += ch.get_text()
            cur["box"] = (min(cur["box"][0], ch.x0), min(cur["box"][1], ch.y0),
                          max(cur["box"][2], ch.x1), max(cur["box"][3], ch.y1))
            continue
        if cur is not None:
            spans.append(Span(page_no, cur["text"], to_top(cur["box"]), *cur["key"]))
        cur = {"key": key, "text": ch.get_text(), "box": (ch.x0, ch.y0, ch.x1, ch.y1)}
    if cur is not None:
        spans.append(Span(page_no, cur["text"], to_top(cur["box"]), *cur["key"]))
    return [s for s in spans if s.text.strip()]


def read_pdf(path: Path) -> PdfFacts:
    facts = PdfFacts()
    try:
        with open(path, "rb") as fh:
            doc = PDFDocument(PDFParser(fh))
            for info in doc.info:
                for key, value in info.items():
                    text = _text(value).strip()
                    if text:
                        facts.metadata.append((str(key), text))
            xmp = resolve1(doc.catalog.get("Metadata"))
            if isinstance(xmp, PDFStream):
                raw = xmp.get_data().decode("utf-8", "ignore")
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
                if text:
                    facts.metadata.append(("XMP", text))
            rsrc = PDFResourceManager()
            device = _Aggregator(rsrc, laparams=LAParams(all_texts=True))
            interpreter = PDFPageInterpreter(rsrc, device)
            for number, page in enumerate(PDFPage.create_pages(doc), start=1):
                interpreter.process_page(page)
                layout = device.get_result()
                cx0, cy0, cx1, cy1 = page.cropbox

                def to_top(b, cx0=cx0, cy1=cy1):
                    return (b[0] - cx0, cy1 - b[3], b[2] - cx0, cy1 - b[1])

                pf = PageFacts(number, cx1 - cx0, cy1 - cy0)
                for kind, obj in _walk(layout):
                    if kind == "image":
                        pf.image_boxes.append(to_top(obj.bbox))
                    else:
                        pf.spans.extend(_spans(obj, number, to_top))
                for annot in resolve1(page.annots) or []:
                    annot = resolve1(annot)
                    if isinstance(annot, dict) and annot.get("Contents") is not None:
                        text = _text(annot["Contents"]).strip()
                        if text:
                            pf.annotations.append(text)
                facts.pages.append(pf)
    except (PDFPasswordIncorrect, PDFEncryptionError) as exc:
        raise ScanError("The PDF is password-protected.") from exc
    except (PDFSyntaxError, PSException) as exc:
        raise ScanError("The PDF is damaged or not a valid PDF.") from exc
    return facts
