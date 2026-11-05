"""Read a .docx into plain facts: every text run with its effective style, drawings, metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .ooxml import open_zip_safely, parse_xml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS = {"w": W, "wp": WP, "mc": MC}
TWIP_TO_EMU = 635
TEXT_PARTS = ("word/document.xml", "word/header", "word/footer", "word/footnotes.xml",
              "word/endnotes.xml", "word/comments.xml", "word/glossary/document.xml")
METADATA_PARTS = ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml")
HIGHLIGHT_HEX = {
    "black": "000000", "blue": "0000FF", "cyan": "00FFFF", "green": "00FF00", "magenta": "FF00FF",
    "red": "FF0000", "yellow": "FFFF00", "white": "FFFFFF", "darkBlue": "000080", "darkCyan": "008080",
    "darkGreen": "008000", "darkMagenta": "800080", "darkRed": "800000", "darkYellow": "808000",
    "darkGray": "808080", "lightGray": "C0C0C0",
}


def q(tag: str) -> str:
    return f"{{{W}}}{tag}"


@dataclass
class RunFacts:
    part: str
    path: str
    paragraph_path: str
    text: str
    kind: str  # "text" | "deleted" | "field"
    vanish: bool = False
    color: str | None = None
    background: str = "FFFFFF"
    size_half_points: int | None = None


@dataclass
class Drawing:
    part: str
    run_path: str | None
    alt_text: str
    text: str
    off_page: bool


@dataclass
class DocxFacts:
    runs: list[RunFacts] = field(default_factory=list)
    drawings: list[Drawing] = field(default_factory=list)
    metadata: list[tuple[str, str, str]] = field(default_factory=list)
    embedded: list[str] = field(default_factory=list)


def _on(el: etree._Element | None) -> bool:
    return el is not None and (el.get(q("val")) or "true").lower() not in ("0", "false", "off")


class _Styles:
    def __init__(self, root: etree._Element | None):
        self.by_id: dict[str, etree._Element] = {}
        self.default_rpr = None
        self.default_para: str | None = None
        if root is None:
            return
        for s in root.iter(q("style")):
            sid = s.get(q("styleId"))
            if sid:
                self.by_id[sid] = s
            if s.get(q("type")) == "paragraph" and s.get(q("default")) in ("1", "true"):
                self.default_para = sid
        self.default_rpr = root.find("w:docDefaults/w:rPrDefault/w:rPr", NS)

    def chain(self, style_id: str | None) -> list[etree._Element]:
        out, seen = [], set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            style = self.by_id.get(style_id)
            if style is None:
                break
            rpr = style.find("w:rPr", NS)
            if rpr is not None:
                out.append(rpr)
            based = style.find("w:basedOn", NS)
            style_id = based.get(q("val")) if based is not None else None
        return list(reversed(out))


def _apply(props: dict, rpr: etree._Element | None) -> None:
    if rpr is None:
        return
    vanish = rpr.find(q("vanish"))
    if vanish is not None:
        props["vanish"] = _on(vanish)
    if _on(rpr.find(q("specVanish"))):
        props["vanish"] = True
    color = rpr.find(q("color"))
    if color is not None:
        val = color.get(q("val"))
        props["color"] = None if not val or val.lower() == "auto" else val.upper()
    size = rpr.find(q("sz"))
    if size is not None and (size.get(q("val")) or "").isdigit():
        props["sz"] = int(size.get(q("val")))
    shd = rpr.find(q("shd"))
    if shd is not None:
        fill = shd.get(q("fill"))
        if fill and fill.lower() != "auto":
            props["bg"] = fill.upper()
    hl = rpr.find(q("highlight"))
    if hl is not None and HIGHLIGHT_HEX.get(hl.get(q("val"), "")):
        props["bg"] = HIGHLIGHT_HEX[hl.get(q("val"))]


def _ancestor_background(run: etree._Element, page_bg: str) -> str:
    for anc in run.iterancestors():
        local = etree.QName(anc).localname
        shd = None
        if local == "p":
            shd = anc.find("w:pPr/w:shd", NS)
        elif local == "tc":
            shd = anc.find("w:tcPr/w:shd", NS)
        elif local == "tbl":
            shd = anc.find("w:tblPr/w:shd", NS)
        if shd is not None:
            fill = shd.get(q("fill"))
            if fill and fill.lower() != "auto":
                return fill.upper()
    return page_bg


def _page_size_emu(root: etree._Element) -> tuple[int, int]:
    pg = root.find(".//w:sectPr/w:pgSz", NS)
    w = int(pg.get(q("w"), "12240")) if pg is not None else 12240
    h = int(pg.get(q("h"), "15840")) if pg is not None else 15840
    return w * TWIP_TO_EMU, h * TWIP_TO_EMU


def _in_fallback(el: etree._Element) -> bool:
    return any(a.tag == f"{{{MC}}}Fallback" for a in el.iterancestors())


def _read_drawings(part: str, root: etree._Element, page: tuple[int, int]) -> tuple[list[Drawing], set]:
    tree = root.getroottree()
    drawings, off_page_anchors = [], set()
    for anchor in root.iter(f"{{{WP}}}anchor", f"{{{WP}}}inline"):
        if _in_fallback(anchor):
            continue
        docpr = anchor.find("wp:docPr", NS)
        alt = " ".join(filter(None, [docpr.get("title"), docpr.get("descr")])) if docpr is not None else ""
        text = "".join(t.text or "" for t in anchor.iter(q("t")))
        off = False
        if anchor.tag == f"{{{WP}}}anchor":
            ext = anchor.find("wp:extent", NS)
            cx = int(ext.get("cx", "0")) if ext is not None else 0
            cy = int(ext.get("cy", "0")) if ext is not None else 0
            off = _offset_outside(anchor, "H", cx, page[0]) or _offset_outside(anchor, "V", cy, page[1])
        if off:
            off_page_anchors.add(anchor)
        run = next(anchor.iterancestors(q("r")), None)
        drawings.append(Drawing(part, tree.getpath(run) if run is not None else None, alt, text, off))
    return drawings, off_page_anchors


def _offset_outside(anchor: etree._Element, axis: str, size: int, page: int) -> bool:
    el = anchor.find(f"wp:position{axis}/wp:posOffset", NS)
    if el is None or not (el.text or "").strip().lstrip("-").isdigit():
        return False
    value = int(el.text.strip())
    return value > page or value + size < 0


def _read_runs(part: str, root: etree._Element, styles: _Styles, page_bg: str, skip: set) -> list[RunFacts]:
    tree = root.getroottree()
    out = []
    for r in root.iter(q("r")):
        if _in_fallback(r) or any(a in skip for a in r.iterancestors()):
            continue
        texts, kind = [], "text"
        for child in r:
            if child.tag == q("t"):
                texts.append(child.text or "")
            elif child.tag == q("delText"):
                texts.append(child.text or "")
                kind = "deleted"
            elif child.tag == q("instrText"):
                texts.append(child.text or "")
                kind = "field"
            elif child.tag == q("tab"):
                texts.append("\t")
        text = "".join(texts)
        if not text:
            continue
        if kind == "text" and any(a.tag in (q("del"), q("moveFrom")) for a in r.iterancestors()):
            kind = "deleted"
        p = next(r.iterancestors(q("p")), None)
        pstyle = p.find("w:pPr/w:pStyle", NS) if p is not None else None
        rstyle = r.find("w:rPr/w:rStyle", NS)
        props: dict = {}
        _apply(props, styles.default_rpr)
        for rpr in styles.chain(pstyle.get(q("val")) if pstyle is not None else styles.default_para):
            _apply(props, rpr)
        if rstyle is not None:
            for rpr in styles.chain(rstyle.get(q("val"))):
                _apply(props, rpr)
        _apply(props, r.find(q("rPr")))
        out.append(RunFacts(
            part=part,
            path=tree.getpath(r),
            paragraph_path=tree.getpath(p) if p is not None else tree.getpath(r),
            text=text,
            kind=kind,
            vanish=props.get("vanish", False),
            color=props.get("color"),
            background=props.get("bg") or _ancestor_background(r, page_bg),
            size_half_points=props.get("sz"),
        ))
    return out


def read_docx(path: Path) -> DocxFacts:
    facts = DocxFacts()
    with open_zip_safely(path) as zf:
        names = zf.namelist()
        if "word/document.xml" not in names:
            from ..errors import ScanError
            raise ScanError("This zip file is not a Word document.")
        styles = _Styles(parse_xml(zf.read("word/styles.xml")) if "word/styles.xml" in names else None)
        document = parse_xml(zf.read("word/document.xml"))
        bg_el = document.find("w:background", NS)
        page_bg = (bg_el.get(q("color")) or "FFFFFF").upper() if bg_el is not None else "FFFFFF"
        if page_bg == "AUTO":
            page_bg = "FFFFFF"
        page = _page_size_emu(document)
        for name in names:
            if not name.startswith(TEXT_PARTS) or not name.endswith(".xml"):
                continue
            root = document if name == "word/document.xml" else parse_xml(zf.read(name))
            drawings, off_page = _read_drawings(name, root, page)
            facts.drawings.extend(drawings)
            facts.runs.extend(_read_runs(name, root, styles, page_bg, off_page))
        for name in METADATA_PARTS:
            if name in names:
                for el in parse_xml(zf.read(name)).iter():
                    if isinstance(el.tag, str) and len(el) == 0 and (el.text or "").strip():
                        facts.metadata.append((name, etree.QName(el).localname, el.text.strip()))
        facts.embedded = sorted(n for n in names if n.startswith("word/embeddings/"))
    return facts
