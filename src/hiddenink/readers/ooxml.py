"""Safe access to zip-based Office files."""
from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from ..errors import ScanError, UnsafeFile

MAX_MEMBERS = 5000
MAX_TOTAL_BYTES = 500 * 1024 * 1024  # files up to 250 MB, including everything on the website


def max_expansion(size: int) -> int:
    """How far a Word file may expand. Only very large local files (up to 2 GB) get more: twice their size."""
    return max(MAX_TOTAL_BYTES, 2 * size)
MAX_RATIO = 100
RATIO_CHECK_MIN = 1_000_000

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def open_zip_safely(path: Path) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ScanError("The file is damaged, password-protected, or not a valid Office document.") from exc
    infos = zf.infolist()
    if len(infos) > MAX_MEMBERS:
        raise UnsafeFile(f"The file contains more than {MAX_MEMBERS} internal parts.")
    limit = max_expansion(path.stat().st_size)
    if sum(i.file_size for i in infos) > limit:
        raise UnsafeFile(f"The file expands to more than {limit // (1024 * 1024)} MB.")
    for info in infos:
        if info.file_size > RATIO_CHECK_MIN and info.file_size / max(info.compress_size, 1) > MAX_RATIO:
            raise UnsafeFile("The file looks like a zip bomb (extreme compression ratio).")
        if info.flag_bits & 0x1:
            raise ScanError("The file is password-protected.")
    return zf


def parse_xml(data: bytes) -> etree._Element:
    try:
        return etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError as exc:
        raise ScanError("The document contains malformed XML.") from exc
