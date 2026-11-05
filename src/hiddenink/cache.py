"""Remember scan summaries by file hash so unchanged files are instant the second time."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

from . import __version__
from .brief import make_brief
from .scan import scan_file

MAX_AGE_SECONDS = 30 * 86400


def cache_dir() -> Path:
    override = os.environ.get("HIDDENINK_CACHE_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "hiddenink"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hiddenink" / "cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hiddenink"


def _entry(sha256: str) -> Path:
    return cache_dir() / f"{sha256}-{__version__}.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get(sha256: str) -> dict | None:
    try:
        return json.loads(_entry(sha256).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _prune(folder: Path) -> None:
    cutoff = time.time() - MAX_AGE_SECONDS
    for p in folder.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def put(sha256: str, brief: dict) -> None:
    folder = cache_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _prune(folder)
        tmp = _entry(sha256).with_suffix(".tmp")
        tmp.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_entry(sha256))
    except OSError:
        pass  # a cache that cannot be written is only slower, never wrong


def brief_for(path: Path, timeout: float | None = None) -> dict:
    """timeout None: big files get more time (scan.scan_timeout)."""
    path = Path(path)
    sha = file_sha256(path)
    hit = get(sha)
    if hit is not None:
        return {**hit, "file": path.name}
    b = make_brief(scan_file(path, timeout=timeout))
    put(sha, b)
    return b
