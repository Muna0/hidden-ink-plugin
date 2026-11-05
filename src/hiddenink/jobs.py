"""Short-lived scan jobs: one temp folder per upload, deleted after one hour."""
from __future__ import annotations

import re
import secrets
import shutil
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

JOB_TTL_SECONDS = 3600
MAX_NAME_BYTES = 150  # Linux allows 255 bytes per file name; leave room for ".certificate.pdf"
MAX_DISPLAY = 255
_ID = re.compile(r"^[A-Za-z0-9_-]{22}$")
_UNSAFE = re.compile(r"[^\w.\- ]+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _basename(name: str) -> str:
    return Path(unicodedata.normalize("NFC", name).replace("\\", "/")).name


def _cap_bytes(text: str, limit: int) -> str:
    return text.encode()[:limit].decode("utf-8", "ignore")


def display_name(name: str, default: str = "document") -> str:
    """The file name as the person typed it, for reports, the certificate, and the screen."""
    base = _basename(_CONTROL.sub("", name)).strip()
    return base[:MAX_DISPLAY] if base else default


def safe_name(name: str, default: str = "document") -> str:
    """A file-system-safe version of a name, for download file names."""
    base = _UNSAFE.sub("_", _basename(name)).strip(" .")
    if not base:
        return default
    if len(base.encode()) > MAX_NAME_BYTES:
        stem, dot, ext = base.rpartition(".")
        if dot and len(ext.encode()) <= 10:
            base = _cap_bytes(stem, MAX_NAME_BYTES - len(ext.encode()) - 1) + "." + ext
        else:
            base = _cap_bytes(base, MAX_NAME_BYTES)
    return base


@dataclass
class Job:
    id: str
    dir: Path
    created: float
    original_name: str
    files: dict[str, str] | None = None
    download_stem: str = "document"


class JobStore:
    def __init__(self, root: Path | None = None, ttl: float = JOB_TTL_SECONDS, clock=time.time):
        self.root = Path(root) if root else Path(tempfile.mkdtemp(prefix="hiddenink-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.clock = clock
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, original_name: str) -> Job:
        self.sweep()
        job_id = secrets.token_urlsafe(16)  # always 22 characters
        folder = self.root / job_id
        folder.mkdir()
        job = Job(job_id, folder, self.clock(), display_name(original_name))
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        if not _ID.match(job_id or ""):
            return None
        self.sweep()
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is not None:
            shutil.rmtree(job.dir, ignore_errors=True)

    def sweep(self) -> int:
        now = self.clock()
        with self._lock:
            expired = [j for j in self._jobs.values() if now - j.created >= self.ttl]
            for job in expired:
                del self._jobs[job.id]
        for job in expired:
            shutil.rmtree(job.dir, ignore_errors=True)
        return len(expired)
