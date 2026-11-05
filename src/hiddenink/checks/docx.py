"""Turn .docx facts into findings."""
from __future__ import annotations

from pathlib import Path

from ..color import contrast_ratio
from ..language import instruction_like
from ..model import Finding, Location, Visibility
from ..readers.docx import RunFacts, read_docx
from .unicode import check_unicode

H, U = Visibility.HIDDEN, Visibility.UNCERTAIN
KNOWN_FIELDS = {
    "ADDIN", "ADVANCE", "ASK", "AUTHOR", "AUTONUM", "AUTOTEXT", "BIBLIOGRAPHY", "CITATION", "COMMENTS",
    "CREATEDATE", "DATE", "DOCPROPERTY", "DOCVARIABLE", "EQ", "FILENAME", "FILLIN", "FORMCHECKBOX",
    "FORMDROPDOWN", "FORMTEXT", "GOTOBUTTON", "HYPERLINK", "IF", "INCLUDEPICTURE", "INCLUDETEXT", "INDEX",
    "KEYWORDS", "LASTSAVEDBY", "LISTNUM", "MACROBUTTON", "MERGEFIELD", "NOTEREF", "NUMPAGES", "NUMWORDS",
    "PAGE", "PAGEREF", "PRINTDATE", "QUOTE", "REF", "SAVEDATE", "SECTION", "SECTIONPAGES", "SEQ", "SET",
    "STYLEREF", "SUBJECT", "SYMBOL", "TA", "TC", "TEMPLATE", "TIME", "TITLE", "TOA", "TOC", "USERNAME", "XE",
}
LONG_HIDDEN_VALUE = 200


def _style_verdict(run: RunFacts) -> tuple[str, Visibility, str] | None:
    size_pt = run.size_half_points / 2 if run.size_half_points is not None else None
    if run.vanish:
        return "docx.vanish", H, "Word's hidden-text setting is on, so this text does not show on screen or in print."
    if size_pt is not None and size_pt < 2:
        return "docx.tiny_font", H, f"Font size is {size_pt:g}pt, too small for a person to read."
    if run.color:
        ratio = contrast_ratio(run.color, run.background)
        if ratio < 1.3:
            return ("docx.low_contrast", H,
                    f"Text color #{run.color} on background #{run.background} is invisible (contrast {ratio:.2f}:1).")
        if ratio < 1.6:
            return ("docx.low_contrast", U,
                    f"Text color #{run.color} on background #{run.background} is barely visible (contrast {ratio:.2f}:1).")
    if size_pt is not None and size_pt < 4:
        return "docx.tiny_font", U, f"Font size is {size_pt:g}pt, very hard to read."
    return None


def scan_docx(path: Path) -> tuple[list[Finding], str]:
    facts = read_docx(path)
    findings: list[Finding] = []
    visible: dict[tuple[str, str], list[str]] = {}
    paragraphs: dict[tuple[str, str], list[str]] = {}
    fields: dict[tuple[str, str], list[RunFacts]] = {}
    current: tuple[tuple, Finding] | None = None

    for r in facts.runs:
        key_p = (r.part, r.paragraph_path)
        if r.kind == "field":
            fields.setdefault(key_p, []).append(r)
            current = None
            continue
        if r.kind == "text":
            paragraphs.setdefault(key_p, []).append(r.text)
        benign = False
        if r.kind == "deleted":
            verdict = ("docx.tracked_deletion", U,
                       "Deleted text from tracked changes is still stored in the file, and many AI tools read it.")
            benign = True
        elif r.part == "word/comments.xml":
            verdict = ("docx.comment", U, "Comment text is stored with the document, and many AI tools read it.")
            benign = True
        else:
            verdict = _style_verdict(r) if r.text.strip() else None
        if verdict is None:
            visible.setdefault(key_p, []).append(r.text)
            current = None
            continue
        technique, visibility, why = verdict
        group = (r.part, r.paragraph_path, technique, visibility)
        if current is not None and current[0] == group:
            current[1].excerpt += r.text
            current[1].targets.append(r.path)
        else:
            f = Finding(technique, visibility, Location(part=r.part, path=r.paragraph_path), r.text, why,
                        benign=benign, targets=[r.path])
            findings.append(f)
            current = (group, f)

    for (part, ppath), runs in fields.items():
        instr = "".join(r.text for r in runs).strip()
        words = instr.split()
        keyword = words[0].upper() if words else ""
        hit, _ = instruction_like(instr)
        if hit or (keyword not in KNOWN_FIELDS and len(instr) > 40):
            findings.append(Finding("docx.field_code", H if hit else U, Location(part=part, path=ppath), instr,
                                    "Field code instructions are stored in the file but not shown on the page.",
                                    targets=[r.path for r in runs]))

    for d in facts.drawings:
        if d.off_page and d.text.strip():
            findings.append(Finding("docx.offpage_textbox", H, Location(part=d.part, path=d.run_path), d.text,
                                    "A text box is placed outside the page, so it never shows.",
                                    targets=[d.run_path] if d.run_path else []))
        if d.alt_text.strip():
            hit, _ = instruction_like(d.alt_text)
            if hit or len(d.alt_text) > LONG_HIDDEN_VALUE:
                findings.append(Finding("docx.alt_text", U, Location(part=d.part, path=d.run_path), d.alt_text,
                                        "Image alt text is not shown on the page, but AI tools read it."))

    for part, name, value in facts.metadata:
        hit, _ = instruction_like(value)
        if hit or len(value) > LONG_HIDDEN_VALUE:
            findings.append(Finding("metadata.field", U, Location(part=part, path=name), value,
                                    f"Document property '{name}' is not shown on the page, but AI tools may read it."))

    for name in facts.embedded:
        findings.append(Finding("docx.embedded_object", U, Location(part=name), name,
                                "An embedded file is stored inside this document.", benign=True))

    for (part, ppath), texts in paragraphs.items():
        for f in check_unicode("".join(texts), Location(part=part, path=ppath)):
            f.targets = [ppath]
            findings.append(f)

    text = "\n".join("".join(parts) for parts in visible.values() if "".join(parts).strip())
    return findings, text
