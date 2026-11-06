"""Entry point: detect the format, scan safely, score, and package the result."""
from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .checks.unicode import strip_invisibles
from .errors import ScanError, UnsafeFile, UnsupportedFormat
from .model import SEVERITY_ORDER, ScanResult
from .sandbox import memory_limit, run_isolated
from .score import finalize

MB = 1024 * 1024
MAX_FILE_BYTES = 2048 * MB  # on the person's own computer: CLI, local app, Claude plugin
HOSTED_MAX_FILE_BYTES = 250 * MB  # the public website
QUICK_TIMEOUT = 30.0
BIG_FILE_BYTES = 100 * MB  # above this a scan gets more time
HOSTED_BIG_TIMEOUT = 120.0
LOCAL_SECONDS_PER_100_MB = 30.0
LOCAL_MAX_TIMEOUT = 600.0
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def size_label(n: int) -> str:
    return f"{n / (1024 * MB):g} GB" if n >= 1024 * MB else f"{n / MB:g} MB"


def too_big(limit: int) -> str:
    return f"The file is larger than the {size_label(limit)} limit."


def scan_timeout(size: int, hosted: bool = False) -> float:
    """Seconds a scan may take. Big files get longer: 2 minutes on the website, scaled with size offline."""
    if size <= BIG_FILE_BYTES:
        return QUICK_TIMEOUT
    if hosted:
        return HOSTED_BIG_TIMEOUT
    return min(LOCAL_MAX_TIMEOUT, LOCAL_SECONDS_PER_100_MB * -(-size // (100 * MB)))


def detect_format(path: Path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(1024)
    if head.startswith(OLE_MAGIC):
        raise ScanError("This is a password-protected or an older (.doc/.xls/.ppt) Office file. "
                        "Hidden Ink cannot scan it yet.")
    # A zip signature at byte 0 wins: a Word file must not be passed off as a PDF by a stray %PDF marker
    if b"%PDF" in head and not head.startswith(b"PK"):
        return "pdf"
    if head.startswith(b"PK"):
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise ScanError("The file is damaged or not a valid Office document.") from exc
        if "word/document.xml" in names:
            return "docx"
    raise UnsupportedFormat("This file type is not supported yet. Hidden Ink currently scans .docx and .pdf files.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file_unsafe(path: Path) -> ScanResult:
    from .checks.docx import scan_docx
    from .checks.pdf import scan_pdf

    fmt = detect_format(path)
    findings, text = {"docx": scan_docx, "pdf": scan_pdf}[fmt](path)
    for f in findings:
        finalize(f)
    findings.sort(key=lambda f: -SEVERITY_ORDER[f.severity])
    return ScanResult(
        file_name=path.name,
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
        file_format=fmt,
        engine_version=__version__,
        scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        findings=findings,
        visible_text=strip_invisibles(text),
    )


def scan_file(path: Path, timeout: float | None = None) -> ScanResult:
    """Scan in a sandbox. With no timeout, big files get more time (see scan_timeout)."""
    path = Path(path)
    if not path.is_file():
        raise ScanError(f"File not found: {path.name}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise UnsafeFile(too_big(MAX_FILE_BYTES))
    return run_isolated(scan_file_unsafe, path, timeout=timeout or scan_timeout(size), memory=memory_limit(size))
