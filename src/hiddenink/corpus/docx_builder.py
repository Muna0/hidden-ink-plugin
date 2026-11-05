"""Build small .docx files from raw XML for tests, demos, and the benchmark."""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOC_NS = (
    f'xmlns:w="{W_NS}" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
)
HIDDEN_CHAR_STYLES = (
    f'<w:styles xmlns:w="{W_NS}"><w:style w:type="character" w:styleId="Ghost">'
    '<w:name w:val="Ghost"/><w:rPr><w:vanish/></w:rPr></w:style></w:styles>'
)
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="bin" ContentType="application/octet-stream"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def run(text: str, *, vanish: bool = False, color: str | None = None, sz: int | None = None,
        shd: str | None = None, highlight: str | None = None, style: str | None = None) -> str:
    props = []
    if style:
        props.append(f'<w:rStyle w:val="{style}"/>')
    if vanish:
        props.append("<w:vanish/>")
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if sz:
        props.append(f'<w:sz w:val="{sz}"/>')
    if highlight:
        props.append(f'<w:highlight w:val="{highlight}"/>')
    if shd:
        props.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shd}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(*runs: str, shd: str | None = None) -> str:
    ppr = f'<w:pPr><w:shd w:val="clear" w:color="auto" w:fill="{shd}"/></w:pPr>' if shd else ""
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def deleted(text: str) -> str:
    return (f'<w:del w:id="1" w:author="Counsel" w:date="2026-01-01T00:00:00Z"><w:r>'
            f'<w:delText xml:space="preserve">{escape(text)}</w:delText></w:r></w:del>')


def field(instr: str, shown: str = "1") -> str:
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> {escape(instr)} </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f"{run(shown)}"
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def cell(*paras: str, fill: str) -> str:
    return (f'<w:tbl><w:tr><w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="{fill}"/></w:tcPr>'
            f"{''.join(paras)}</w:tc></w:tr></w:tbl>")


def textbox(text: str, x_emu: int, y_emu: int, alt: str = "") -> str:
    return (
        '<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" '
        'behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>{x_emu}</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="page"><wp:posOffset>{y_emu}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="914400" cy="457200"/><wp:docPr id="1" name="Box" descr="{escape(alt, {chr(34): "&quot;"})}"/>'
        '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        f"<wps:wsp><wps:txbx><w:txbxContent>{para(run(text))}</w:txbxContent></wps:txbx></wps:wsp>"
        "</a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>"
    )


def build_docx(path: Path, body: str, *, styles: str | None = None, comments: list[str] | None = None,
               description: str | None = None, embeddings: dict[str, bytes] | None = None,
               raw_document: str | None = None) -> Path:
    document = raw_document or (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {DOC_NS}><w:body>{body}'
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/document.xml", document)
        if styles:
            zf.writestr("word/styles.xml", styles)
        if comments:
            items = "".join(
                f'<w:comment w:id="{i}" w:author="Reviewer"><w:p><w:r><w:t xml:space="preserve">{escape(c)}</w:t></w:r></w:p></w:comment>'
                for i, c in enumerate(comments)
            )
            zf.writestr("word/comments.xml", f'<w:comments xmlns:w="{W_NS}">{items}</w:comments>')
        zf.writestr(
            "docProps/core.xml",
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Agreement</dc:title>'
            f"<dc:description>{escape(description or '')}</dc:description></cp:coreProperties>",
        )
        for name, data in (embeddings or {}).items():
            zf.writestr(f"word/embeddings/{name}", data)
    return path
