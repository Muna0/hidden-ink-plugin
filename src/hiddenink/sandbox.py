"""Run work in a child process with a time limit and (on Linux) a memory limit."""
from __future__ import annotations

import multiprocessing as mp

from . import errors

MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024


def memory_limit(size: int) -> int:
    """Big PDFs need about 2.3 times their size in memory (measured), so the limit grows with the file."""
    return max(MEMORY_LIMIT_BYTES, 3 * size + 1024 * 1024 * 1024)


def _child(conn, fn, args, memory):
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    except (ImportError, ValueError, OSError):
        pass  # macOS does not enforce RLIMIT_AS; the time limit still applies
    try:
        conn.send(("ok", fn(*args)))
    except errors.HiddenInkError as exc:
        conn.send(("known", (type(exc).__name__, str(exc))))
    except MemoryError:
        conn.send(("known", ("UnsafeFile", "The file needs more memory than the safety limit allows.")))
    except Exception:  # noqa: BLE001 - any parser crash becomes a clean user message
        conn.send(("known", ("ScanError", "The file could not be read. It may be damaged or use an unusual structure.")))
    finally:
        conn.close()


def run_isolated(fn, *args, timeout: float, memory: int = MEMORY_LIMIT_BYTES):
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, fn, args, memory), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout):
            raise errors.ScanTimeout(f"The scan took longer than {timeout:g} seconds and was stopped.")
        try:
            status, payload = parent.recv()
        except EOFError as exc:
            raise errors.ScanError("The file crashed the reader and was stopped.") from exc
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        parent.close()
    if status == "ok":
        return payload
    name, message = payload
    raise getattr(errors, name, errors.ScanError)(message)
