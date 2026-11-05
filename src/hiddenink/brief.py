"""A compact, labeled scan summary for Claude: findings only, never the document text."""
from __future__ import annotations

from .labels import location_label, technique_label
from .model import SEVERITY_ORDER, ScanResult, Severity
from .outputs.report import severity_counts

NO_FINDINGS = "No hidden text found by Hidden Ink's checks."
MAX_EXCERPT = 300


def _trim(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_EXCERPT else text[: MAX_EXCERPT - 3] + "..."


def make_brief(result: ScanResult) -> dict:
    alarms = [f for f in result.findings if SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[Severity.MEDIUM]]
    top = result.findings[0].severity.value if result.findings else None
    counts = severity_counts(result)
    if alarms:
        parts = [f"{counts[s.value]} {s.value}" for s in Severity if counts[s.value] and s is not Severity.INFO]
        verdict = f"Hidden text found: {', '.join(parts)}."
    else:
        verdict = NO_FINDINGS
    return {
        "file": result.file_name,
        "sha256": result.sha256,
        "format": result.file_format,
        "verdict": verdict,
        "top_severity": top,
        "counts": counts,
        "findings": [
            {
                "severity": f.severity.value,
                "kind": technique_label(f.technique),
                "technique": f.technique,
                "where": location_label(f.location),
                "excerpt": _trim(f.excerpt),
                "why": f.explanation,
                "instruction_like": f.instruction_like,
            }
            for f in result.findings
        ],
    }
