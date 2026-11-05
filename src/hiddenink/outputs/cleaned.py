"""Write a copy of the document with hidden content removed."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from lxml import etree

from ..checks.unicode import strip_invisibles
from ..model import Finding, ScanResult, Visibility
from ..readers.ooxml import open_zip_safely, parse_xml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PAD = 1.0


def _removable(f: Finding) -> bool:
    return f.visibility is Visibility.HIDDEN and not f.benign


def _clean_docx(src: Path, dst: Path, result: ScanResult) -> None:
    by_part: dict[str, list[Finding]] = {}
    for f in result.findings:
        if _removable(f) and f.location.part:
            by_part.setdefault(f.location.part, []).append(f)
    with open_zip_safely(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            todo = by_part.get(info.filename)
            if todo:
                root = parse_xml(data)
                namespaces = {k: v for el in root.iter() if isinstance(el.tag, str) for k, v in el.nsmap.items() if k}
                remove, strip = [], []
                for f in todo:
                    for xpath in f.targets:
                        for el in root.xpath(xpath, namespaces=namespaces):
                            (strip if f.technique.startswith("unicode.") else remove).append(el)
                for el in strip:
                    for t in el.iter(f"{{{W}}}t"):
                        t.text = strip_invisibles(t.text or "")
                for el in remove:
                    parent = el.getparent()
                    if parent is not None:
                        parent.remove(el)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            zout.writestr(info, data)


def _clean_pdf(src: Path, dst: Path, result: ScanResult) -> None:
    boxes: dict[int, list[tuple[float, float, float, float]]] = {}
    for f in result.findings:
        if _removable(f) and f.location.page is not None and f.location.bbox is not None:
            boxes.setdefault(f.location.page, []).append(f.location.bbox)
    pdf = pdfium.PdfDocument(str(src))
    try:
        for number, page_boxes in boxes.items():
            page = pdf[number - 1]
            cl, _cb, _cr, ct = page.get_cropbox()
            removed = False
            objects = list(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_TEXT]))
            for obj in objects:
                left, bottom, right, top = obj.get_bounds()
                cx, cy = (left + right) / 2 - cl, ct - (bottom + top) / 2
                if any(x0 - PAD <= cx <= x1 + PAD and y0 - PAD <= cy <= y1 + PAD for x0, y0, x1, y1 in page_boxes):
                    page.remove_obj(obj)
                    obj.close()  # detached objects are owned by the caller
                    removed = True
            del objects
            if removed:
                page.gen_content()
            page.close()
        pdf.save(str(dst))
    finally:
        pdf.close()


def clean_copy(src: Path, dst: Path, result: ScanResult) -> Path:
    src, dst = Path(src), Path(dst)
    if result.file_format == "docx":
        _clean_docx(src, dst, result)
    elif result.file_format == "pdf":
        _clean_pdf(src, dst, result)
    else:
        raise ValueError(f"No cleaner for {result.file_format}")
    return dst
