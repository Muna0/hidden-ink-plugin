"""Invisible and deceptive Unicode characters."""
from __future__ import annotations

import re
import unicodedata

from ..model import Finding, Location, Visibility

TAGS = range(0xE0000, 0xE0080)
ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x180E}
VARIATION = set(range(0xFE00, 0xFE10)) | set(range(0xE0100, 0xE01F0))
BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
DEPRECATED = set(range(0x206A, 0x2070))
INVISIBLE = set(TAGS) | ZERO_WIDTH | VARIATION | BIDI | DEPRECATED
CONFUSABLE_SCRIPTS = {"CYRILLIC", "GREEK"}


def _max_run(text: str, members: set[int] | range) -> int:
    best = cur = 0
    for ch in text:
        cur = cur + 1 if ord(ch) in members else 0
        best = max(best, cur)
    return best


def show_invisibles(text: str, limit: int = 300) -> str:
    out = "".join(f"[U+{ord(c):04X}]" if ord(c) in INVISIBLE else c for c in text)
    return out if len(out) <= limit else out[: limit - 3] + "..."


def strip_invisibles(text: str) -> str:
    return "".join(c for c in text if ord(c) not in INVISIBLE)


def _script(ch: str) -> str:
    return unicodedata.name(ch, "UNKNOWN").split(" ")[0]


def check_unicode(text: str, location: Location) -> list[Finding]:
    findings: list[Finding] = []

    def add(technique: str, visibility: Visibility, excerpt: str, why: str) -> None:
        findings.append(Finding(technique, visibility, location, excerpt, why))

    tag_text = "".join(chr(ord(c) - 0xE0000) for c in text if ord(c) in TAGS and 0x20 <= ord(c) - 0xE0000 < 0x7F)
    if any(ord(c) in TAGS for c in text):
        add("unicode.tag_chars", Visibility.HIDDEN, tag_text or show_invisibles(text),
            "Invisible Unicode tag characters spell out text that AI systems can read.")

    body = text[1:] if text.startswith("\ufeff") else text
    zw_total = sum(1 for c in body if ord(c) in ZERO_WIDTH)
    if _max_run(body, ZERO_WIDTH) >= 3 or zw_total >= 5:
        add("unicode.zero_width", Visibility.HIDDEN, show_invisibles(text),
            "A run of zero-width characters can carry a hidden message.")

    if _max_run(text, VARIATION) >= 3:
        add("unicode.variation_selectors", Visibility.HIDDEN, show_invisibles(text),
            "A run of variation selectors can encode hidden data.")

    if any(ord(c) in BIDI for c in text):
        add("unicode.bidi_controls", Visibility.UNCERTAIN, show_invisibles(text),
            "Direction-override characters can make text display differently from how it is read.")

    if any(ord(c) in DEPRECATED for c in text):
        add("unicode.deprecated_format", Visibility.HIDDEN, show_invisibles(text),
            "Deprecated invisible formatting characters have no legitimate use in documents.")

    for word in re.findall(r"\w+", text):
        scripts = {_script(c) for c in word if c.isalpha()}
        if "LATIN" in scripts and scripts & CONFUSABLE_SCRIPTS:
            add("unicode.mixed_script", Visibility.UNCERTAIN, word,
                "This word mixes Latin letters with look-alike letters from another alphabet.")
            break

    return findings
