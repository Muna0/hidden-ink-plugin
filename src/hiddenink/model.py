from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Visibility(str, Enum):
    HIDDEN = "hidden"
    UNCERTAIN = "uncertain"
    VISIBLE = "visible"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    INFO = "info"


SEVERITY_ORDER = {Severity.CRITICAL: 3, Severity.HIGH: 2, Severity.MEDIUM: 1, Severity.INFO: 0}


@dataclass(frozen=True)
class Location:
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None  # points, origin top-left of visible page
    part: str | None = None  # file part inside a zip format, e.g. "word/document.xml"
    path: str | None = None  # XPath inside the part


@dataclass
class Finding:
    technique: str
    visibility: Visibility
    location: Location
    excerpt: str
    explanation: str
    benign: bool = False
    instruction_like: bool = False
    instruction_reason: str | None = None
    severity: Severity = Severity.INFO
    targets: list[str] = field(default_factory=list)  # XPaths to remove when cleaning


@dataclass
class ScanResult:
    file_name: str
    sha256: str
    size_bytes: int
    file_format: str
    engine_version: str
    scanned_at: str
    mode: str = "quick"
    findings: list[Finding] = field(default_factory=list)
    visible_text: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
