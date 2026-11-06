"""HTTP API plus the built web app. The same code runs locally (`hiddenink serve`) and hosted."""
from __future__ import annotations

import os
import shutil
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from . import __version__
from .checks.unicode import show_invisibles
from .errors import HiddenInkError, ScanError, ScanTimeout, UnsafeFile, UnsupportedFormat
from .jobs import Job, JobStore, safe_name
from .outputs.bundle import DOWNLOADS, process_upload
from .outputs.report import severity_counts
from .sandbox import memory_limit, run_isolated
from .samples import SAMPLES, build_sample
from . import scan as engine
from .scan import HOSTED_MAX_FILE_BYTES, MAX_FILE_BYTES, detect_format, scan_timeout, too_big

STATIC_DIR = Path(__file__).parent / "webapp"
BUNDLE_EXTRA = 30  # previews and downloads, on top of the scan time
MAX_CONCURRENT_SCANS = 2
# One big file at a time (a big PDF needs about 720 MB of memory). A second one is turned away at once
# rather than waiting, so it never holds a shared scan slot that small files need.
FORM_OVERHEAD = 1_000_000
CHUNK = 1 << 20
SWEEP_SECONDS = 60
GONE = "This scan has expired or does not exist. Scan the file again."
UNEXPECTED = "Something went wrong on our side. Try again."
DISK_STEM = "document"
STATUS = {UnsupportedFormat: 415, UnsafeFile: 413, ScanTimeout: 422}
SCANS_PER_WINDOW = 30  # per visitor, so one person cannot hold the scanner for everyone else
WINDOW_SECONDS = 600
MIN_FREE_BYTES = 1536 * 1024 * 1024  # stop accepting scans before uploads can fill the disk
BUSY = "Hidden Ink is busy right now. Try again in a few minutes."
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _max_upload(hosted: bool) -> int:
    return HOSTED_MAX_FILE_BYTES if hosted else MAX_FILE_BYTES


def _save_upload(file: UploadFile, dst: Path, limit: int) -> None:
    size = 0
    with open(dst, "wb") as out:
        while chunk := file.file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                raise UnsafeFile(too_big(limit))
            out.write(chunk)
    if size == 0:
        raise ScanError("The file is empty.")


def _payload(job: Job, result, bundle: dict, ttl: float) -> dict:
    data = result.to_dict()
    data.pop("visible_text", None)
    for finding in data["findings"]:
        finding.pop("targets", None)
        finding["display_excerpt"] = show_invisibles(finding["excerpt"].strip(), limit=600)
    preview = bundle["preview"]
    if preview["kind"] == "pages":
        for page in preview["pages"]:
            page["image"] = f"/api/scans/{job.id}/pages/{page['number']}"
    return {
        "id": job.id,
        "expires_in": int(ttl),
        "result": data,
        "counts": severity_counts(result),
        "preview": preview,
        "downloads": {key: f"/api/scans/{job.id}/download/{key}" for key in bundle["files"]},
    }


def create_app(store: JobStore | None = None, static_dir: Path | None = STATIC_DIR,
               hosted: bool | None = None) -> FastAPI:
    """hosted: the public website (250 MB, 2 minute big scans). Defaults to the HIDDENINK_HOSTED=1 setting."""
    store = store or JobStore()
    hosted = os.environ.get("HIDDENINK_HOSTED") == "1" if hosted is None else hosted
    gate = threading.BoundedSemaphore(MAX_CONCURRENT_SCANS)
    big_gate = threading.BoundedSemaphore(1)
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(_app):
        def sweeper():
            while not stop.wait(SWEEP_SECONDS):
                store.sweep()

        threading.Thread(target=sweeper, daemon=True).start()
        yield
        stop.set()
        shutil.rmtree(store.root, ignore_errors=True)

    app = FastAPI(title="Hidden Ink", version=__version__, docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.max_upload_bytes = _max_upload(hosted)
    app.state.big_gate = big_gate

    recent: dict[str, deque] = defaultdict(deque)
    recent_lock = threading.Lock()

    def over_limit(visitor: str) -> bool:
        now = time.monotonic()
        with recent_lock:
            q = recent[visitor]
            while q and now - q[0] > WINDOW_SECONDS:
                q.popleft()
            if len(q) >= SCANS_PER_WINDOW:
                return True
            q.append(now)
            return False

    @app.middleware("http")
    async def guard(request: Request, call_next):
        is_scan = request.method == "POST" and (request.url.path == "/api/scans" or request.url.path.startswith("/api/samples/"))
        if is_scan:
            # Fly's proxy sets Fly-Client-IP itself, so a visitor cannot pick their own
            visitor = request.headers.get("fly-client-ip") or (request.client.host if request.client else "unknown")
            if over_limit(visitor):
                return _error(429, "Too many scans from your connection. Wait a few minutes and try again.")
            if shutil.disk_usage(store.root).free < MIN_FREE_BYTES:
                return _error(503, BUSY)
        if request.method == "POST" and request.url.path == "/api/scans":
            length = request.headers.get("content-length", "")
            if not length.isdigit():
                return _error(411, "The upload must include its size.")
            limit = _max_upload(hosted)
            if int(length) > limit + FORM_OVERHEAD:
                return _error(413, too_big(limit))
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - never leak a traceback or file name to the client or the log
            response = _error(500, UNEXPECTED)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif path.startswith("/assets/"):  # file names carry a content hash, so they never change
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:  # pages: always check for a newer deploy, or an old page could point at deleted assets
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.exception_handler(HiddenInkError)
    async def known_error(_request, exc: HiddenInkError):
        return _error(STATUS.get(type(exc), 422), str(exc))

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc: HTTPException):
        return _error(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def bad_request(_request, _exc):
        return _error(422, "Choose a .docx or .pdf file to scan.")

    def _job_or_404(job_id: str) -> Job:
        job = store.get(job_id)
        if job is None or job.files is None:
            raise HTTPException(404, GONE)
        return job

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__}

    def _scan_into_job(job: Job, src: Path) -> dict:
        """Run the full pipeline on a file already saved in the job, then return the API payload."""
        fmt = detect_format(src)
        src = src.rename(src.parent / f"{DISK_STEM}.{fmt}")  # fixed name on disk; the real name never touches it
        name = job.original_name
        job.download_stem = safe_name(name[: -len(fmt) - 1] if name.lower().endswith(f".{fmt}") else name)
        size = src.stat().st_size
        big = size > engine.BIG_FILE_BYTES
        if big and not big_gate.acquire(blocking=False):
            raise HTTPException(503, "Hidden Ink is busy with another large file. Try again in a few minutes.")
        try:
            result, bundle = run_isolated(process_upload, src, job.dir / "out", DISK_STEM, name,
                                          timeout=scan_timeout(size, hosted) + BUNDLE_EXTRA,
                                          memory=memory_limit(size))
        finally:
            if big:
                big_gate.release()
        job.files = bundle["files"]
        return _payload(job, result, bundle, store.ttl)

    def _guarded(job_name: str, fill) -> dict:
        if not gate.acquire(timeout=60):
            raise HTTPException(503, "Hidden Ink is busy. Try again in a minute.")
        job = store.create(job_name)
        upload_dir = job.dir / "upload"
        try:
            upload_dir.mkdir()
            return _scan_into_job(job, fill(upload_dir))
        except BaseException:
            store.delete(job.id)
            raise
        finally:
            shutil.rmtree(upload_dir, ignore_errors=True)
            gate.release()

    @app.post("/api/scans")
    def create_scan(file: UploadFile = File(...)):
        def fill(upload_dir: Path) -> Path:
            src = upload_dir / "upload"
            _save_upload(file, src, _max_upload(hosted))
            return src
        return _guarded(file.filename or "document", fill)

    @app.post("/api/samples/{name}/scan")
    def scan_sample(name: str):
        if name not in SAMPLES:
            raise HTTPException(404, "There is no sample with that name.")
        return _guarded(SAMPLES[name].file_name, lambda upload_dir: build_sample(name, upload_dir))

    @app.get("/api/scans/{job_id}/pages/{number}")
    def page_image(job_id: str, number: int):
        path = _job_or_404(job_id).dir / "out" / "pages" / f"page-{number}.png"
        if not path.is_file():
            raise HTTPException(404, "That page is not in the preview.")
        return FileResponse(path, media_type="image/png")

    @app.get("/api/scans/{job_id}/download/{kind}")
    def download(job_id: str, kind: str):
        job = _job_or_404(job_id)
        if kind not in job.files:
            raise HTTPException(404, "That download does not exist.")
        name = job.files[kind]
        return FileResponse(job.dir / "out" / name, media_type=DOWNLOADS[kind],
                            filename=job.download_stem + name[len(DISK_STEM):])

    @app.delete("/api/scans/{job_id}", status_code=204)
    def delete_scan(job_id: str):
        store.delete(_job_or_404(job_id).id)
        return Response(status_code=204)

    if static_dir is not None and (Path(static_dir) / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app
