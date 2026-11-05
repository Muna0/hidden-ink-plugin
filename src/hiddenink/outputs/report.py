"""Human and machine reports."""
from __future__ import annotations

import html
import json

from ..model import SEVERITY_ORDER, Location, ScanResult, Severity


def describe_location(loc: Location) -> str:
    if loc.page is not None:
        return f"page {loc.page}"
    if loc.part:
        return loc.part
    if loc.path:
        return f"document property {loc.path}"
    return "document"


def severity_counts(result: ScanResult) -> dict[str, int]:
    counts = {s.value: 0 for s in Severity}
    for f in result.findings:
        counts[f.severity.value] += 1
    return counts


def has_alarms(result: ScanResult) -> bool:
    return any(SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[Severity.MEDIUM] for f in result.findings)


def to_json(result: ScanResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


def _summary(result: ScanResult) -> str:
    counts = severity_counts(result)
    parts = [f"{n} {k}" for k, n in counts.items() if n]
    return ", ".join(parts) if parts else "no hidden content found"


def to_text(result: ScanResult) -> str:
    lines = [f"{result.file_name}  [{_summary(result)}]  sha256 {result.sha256[:16]}"]
    for f in result.findings:
        excerpt = f.excerpt.strip().replace("\n", " ")
        excerpt = excerpt if len(excerpt) <= 160 else excerpt[:157] + "..."
        lines.append(f"  {f.severity.value.upper():8}  {f.technique}  {describe_location(f.location)}")
        lines.append(f'      "{excerpt}"')
        lines.append(f"      {f.explanation}")
    return "\n".join(lines)


def to_html(result: ScanResult) -> str:
    e = html.escape
    rows = "".join(
        f"<tr class='{e(f.severity.value)}'><td>{e(f.severity.value.upper())}</td><td>{e(f.technique)}</td>"
        f"<td>{e(describe_location(f.location))}</td><td>{e(f.excerpt)}</td><td>{e(f.explanation)}</td></tr>"
        for f in result.findings
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Hidden Ink report</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ccc;padding:.4rem;vertical-align:top}.critical td:first-child{color:#b00020}"
        ".high td:first-child{color:#7c3aed}</style></head><body>"
        f"<h1>Hidden Ink report: {e(result.file_name)}</h1><p>{e(_summary(result))}. "
        f"SHA-256 {e(result.sha256)}. Scanned {e(result.scanned_at)} with Hidden Ink {e(result.engine_version)}.</p>"
        "<table><tr><th>Severity</th><th>Technique</th><th>Location</th><th>Hidden text</th><th>Why it matters</th></tr>"
        f"{rows}</table></body></html>"
    )
