# Hidden Ink for Claude

Hidden Ink finds text in Word (.docx) and PDF files that an AI can read but a person cannot see: white text, hidden Word text, tiny fonts, text off the page, text covered by shapes, comments, deleted tracked changes, field codes, document properties and invisible characters. Hidden instructions like these can steer an AI's summary or review of a contract, filing or résumé without anyone noticing.

Hidden Ink was created by Muna Omar. It is rule-based: it reads the file's structure directly and gives the same result every time. It does not use AI to scan.

## What you get

- **Automatic guard (Claude Code).** Before Claude opens a .docx or .pdf file, Hidden Ink checks it. If it finds high-risk hidden text, it stops Claude from reading the original and tells Claude to read only the visible text instead. Lower-risk findings are passed to Claude as a warning. The guard never approves a tool call on your behalf; your normal permission prompts still apply.
- **Two tools.** `scan_document` reports what is hidden, where it is (page, header, footer, comment and so on) and why it was flagged. `get_clean_text` returns only the text a person can see.
- **A command.** Run `/hidden-ink:scan <file>` at any time.

When nothing is found, Hidden Ink says "No hidden text found by Hidden Ink's checks." It never says a file is safe.

## Install

Hidden Ink needs `uv`, a free Python launcher:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, in Claude Code:

```
/plugin marketplace add Muna0/hidden-ink-plugin
/plugin install hidden-ink@hidden-ink
```

## What runs on your computer

- **Your documents are never uploaded.** Every scan runs on your computer. Hidden Ink makes no network calls of its own.
- **One download on first use.** The first time it starts, `uv` downloads Python (if needed) and the libraries listed in `uv.lock` from PyPI, about 100 MB. The versions are pinned by the lock file. After that, nothing is downloaded. Some firm-managed laptops block this; ask IT to allow `uv` and PyPI.
- **The guard.** A Claude Code hook (`hooks/guard.sh`) reads each Read or Bash tool call that mentions a .docx or .pdf file, scans the files it names, and replies to Claude Code. Other tool calls are passed through untouched in a few milliseconds.
- **A local cache.** Results are kept for 30 days in your user cache folder (`~/Library/Caches/hiddenink` on a Mac), keyed by a fingerprint (SHA-256) of the file, so an unchanged file is not scanned twice. The cache holds findings only, never the document's text.
- **Safety limits.** Each scan runs in a separate process with a time limit. Files up to 2 GB are accepted; files over 100 MB get more time.

The guard covers the normal ways Claude Code opens these files. It is a safety net, not a guarantee.

## Legal

Hidden Ink reports hidden content found by automated analysis. It is not legal advice.

Copyright Muna Omar. All rights reserved. The license for public release has not been chosen yet.
