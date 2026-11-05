"""PDF audit certificate."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..checks.unicode import show_invisibles
from ..model import ScanResult
from .report import describe_location, severity_counts

DISCLAIMER = "This certificate records hidden content detected by automated analysis. It is not legal advice."
VIOLET = colors.HexColor("#6D28D9")


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(54, 30, DISCLAIMER)
    canvas.drawRightString(LETTER[0] - 54, 30, f"Page {doc.page}")
    canvas.restoreState()


def make_certificate(result: ScanResult, out_path: Path) -> Path:
    styles = getSampleStyleSheet()
    cell = styles["BodyText"]
    cell.fontSize, cell.leading = 8, 10
    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER, title="Hidden Ink Audit Certificate",
                            leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    counts = severity_counts(result)
    meta = [
        ["File", result.file_name],
        ["SHA-256", Paragraph(result.sha256, cell)],
        ["Scanned", result.scanned_at],
        ["Engine", f"Hidden Ink {result.engine_version} ({result.mode} scan)"],
        ["Findings", ", ".join(f"{n} {k}" for k, n in counts.items())],
    ]
    meta_table = Table(meta, colWidths=[80, 424])
    meta_table.setStyle(TableStyle([("FONT", (0, 0), (0, -1), "Helvetica-Bold"),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    story = [Paragraph("Hidden Ink Audit Certificate", styles["Title"]), Spacer(1, 6), meta_table, Spacer(1, 14)]
    if not result.findings:
        story.append(Paragraph("No hidden content was detected.", styles["Heading2"]))
    else:
        rows = [["Severity", "Technique", "Location", "Hidden text"]]
        for f in result.findings:
            excerpt = show_invisibles(f.excerpt.strip(), limit=200)
            rows.append([f.severity.value.upper(), Paragraph(escape(f.technique), cell),
                         Paragraph(escape(describe_location(f.location)), cell), Paragraph(escape(excerpt), cell)])
        table = Table(rows, colWidths=[60, 110, 110, 224], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VIOLET),
                                   ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                   ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                                   ("FONTSIZE", (0, 0), (-1, -1), 8),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
        story += [Paragraph("Findings", styles["Heading2"]), table]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return Path(out_path)
