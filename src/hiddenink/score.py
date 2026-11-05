from __future__ import annotations

from .language import instruction_like
from .model import Finding, Severity, Visibility


def severity_for(visibility: Visibility, instruction: bool, benign: bool) -> Severity:
    if benign:
        return Severity.HIGH if instruction else Severity.INFO
    if visibility is Visibility.HIDDEN:
        return Severity.CRITICAL if instruction else Severity.HIGH
    if visibility is Visibility.UNCERTAIN:
        return Severity.HIGH if instruction else Severity.MEDIUM
    return Severity.MEDIUM if instruction else Severity.INFO


def finalize(f: Finding) -> Finding:
    hit, reason = instruction_like(f.excerpt)
    f.instruction_like, f.instruction_reason = hit, reason
    f.severity = severity_for(f.visibility, hit, f.benign)
    return f
