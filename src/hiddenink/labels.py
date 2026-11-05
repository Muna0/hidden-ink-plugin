"""Plain-language names for techniques and locations. Mirrors web/src/labels.ts."""
from __future__ import annotations

from .model import Location

TECHNIQUES = {
    "docx.vanish": "Hidden text setting",
    "docx.low_contrast": "Text matches its background",
    "docx.tiny_font": "Tiny text",
    "docx.field_code": "Field code",
    "docx.offpage_textbox": "Text box off the page",
    "docx.alt_text": "Image alt text",
    "docx.tracked_deletion": "Deleted tracked change",
    "docx.comment": "Comment",
    "docx.embedded_object": "Embedded file",
    "pdf.low_contrast": "Text matches its background",
    "pdf.tiny_font": "Tiny text",
    "pdf.off_page": "Text off the page",
    "pdf.invisible_render_mode": "Invisible text mode",
    "pdf.covered_text": "Text covered by a shape",
    "pdf.annotation": "Hidden annotation",
    "pdf.ocr_layer": "Scan text layer",
    "pdf.gpo_stamp": "Government print stamp",
    "metadata.field": "Document property",
    "unicode.tag_chars": "Invisible tag characters",
    "unicode.zero_width": "Zero-width characters",
    "unicode.variation_selectors": "Variation selector characters",
    "unicode.bidi_controls": "Text direction controls",
    "unicode.deprecated_format": "Deprecated format characters",
    "unicode.mixed_script": "Look-alike letters",
}

PARTS = [
    ("word/document.xml", "Body"), ("word/header", "Header"), ("word/footer", "Footer"),
    ("word/footnotes.xml", "Footnotes"), ("word/endnotes.xml", "Endnotes"), ("word/comments.xml", "Comments"),
    ("word/glossary", "Building blocks"), ("word/embeddings/", "Embedded file"), ("docProps/", "Document properties"),
]


def technique_label(technique: str) -> str:
    return TECHNIQUES.get(technique, technique)


def location_label(loc: Location) -> str:
    if loc.page is not None:
        return f"Page {loc.page}"
    if loc.part:
        return next((label for prefix, label in PARTS if loc.part.startswith(prefix)), loc.part)
    if loc.path:
        return f'Document property "{loc.path}"'
    return "Document"
