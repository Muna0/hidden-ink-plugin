"""Write every download, and the viewer preview, for one scan into a folder."""
from __future__ import annotations

from pathlib import Path

from ..model import ScanResult
from .certificate import make_certificate
from .clean_text import make_clean_text
from .cleaned import clean_copy
from .report import to_html, to_json

DOWNLOADS = {
    "report_json": "application/json",
    "report_html": "text/html",
    "certificate": "application/pdf",
    "clean_text": "text/plain",
    "cleaned": "application/octet-stream",
}


def write_bundle(src: Path, result: ScanResult, out: Path, stem: str, preview: bool = True) -> dict:
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "report_json": f"{stem}.report.json",
        "report_html": f"{stem}.report.html",
        "certificate": f"{stem}.certificate.pdf",
        "clean_text": f"{stem}.clean.txt",
        "cleaned": f"{stem}.cleaned{src.suffix}",
    }
    (out / files["report_json"]).write_text(to_json(result), encoding="utf-8")
    (out / files["report_html"]).write_text(to_html(result), encoding="utf-8")
    (out / files["clean_text"]).write_text(make_clean_text(result), encoding="utf-8")
    make_certificate(result, out / files["certificate"])
    clean_copy(src, out / files["cleaned"], result)
    view = None
    if preview:
        from ..preview import build_preview

        view = build_preview(src, result, out / "pages")
    return {"files": files, "preview": view}


def process_upload(src: Path, out: Path, stem: str, file_name: str | None = None) -> tuple[ScanResult, dict]:
    from ..scan import scan_file_unsafe

    result = scan_file_unsafe(Path(src))
    if file_name:
        result.file_name = file_name  # the name the person uploaded, shown on reports and the certificate
    return result, write_bundle(src, result, out, stem)
