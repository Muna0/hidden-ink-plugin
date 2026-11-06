![Hidden Ink logo](images/logo.png)

# Hidden Ink for Claude Code

**Your AI reads every word of a document. Even the ones you can't see.**

Hidden Ink finds text in Word (.docx) and PDF files that an AI can read but a person cannot see: white text on a white page, 1.5-point fonts, hidden Word text, text off the page or under a shape, comments, deleted tracked changes, field codes, document properties and invisible characters. Hidden instructions like these can quietly steer an AI's summary or review of a contract, court filing, résumé or lease.

Hidden Ink checks every document before Claude reads it, shows you what was hidden and where, and gives Claude only the text a person can see. Created by Muna Omar. Built in Minnesota. Website: [hiddenink.io](https://hiddenink.io)

![A contract under Hidden Ink's UV view: the hidden lines glow where they sit on the page](images/uv-reveal.png)

## See it work

Ask Claude about a document the way you normally would. Hidden Ink checks the file first:

![Claude Code loads the Hidden Ink scanner before reading the document](images/claude-code-checks-first.png)

If the file hides text, Claude works from the visible text only, tells you exactly what was hidden and where, and does not follow hidden instructions:

![Claude Code lists the two hidden instructions Hidden Ink found and says it did not follow them](images/claude-code-what-it-found.png)

## What you get

- **Automatic guard.** Before Claude opens a .docx or .pdf file, Hidden Ink checks it. High-risk hidden text blocks the original and Claude reads the visible text instead. Lower-risk findings reach Claude as a warning. The guard never approves a tool call for you; your normal permission prompts still apply.
- **Two tools.** `scan_document` reports what is hidden, where (page, header, footer, comment and so on) and why it was flagged. `get_clean_text` returns only the text a person can see.
- **A command.** Run `/hidden-ink:scan <file>` any time.
- **Honest results.** When nothing is found, Hidden Ink says "No hidden text found by Hidden Ink's checks." It never says a file is safe.

In testing on 35 legal documents, Hidden Ink caught 22 of 22 hiding techniques with no false alarms on the 13 clean files.

## Install

Hidden Ink needs `uv`, a free Python launcher. In your Mac or Linux terminal:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, inside Claude Code:

```
/plugin marketplace add Muna0/hidden-ink-plugin
/plugin install hidden-ink@hidden-ink
```

The first use downloads about 100 MB once, which takes about 2 minutes. During that time Hidden Ink holds back Word and PDF files with a "finishing setup" note, so nothing is read unchecked.

## Prefer the web?

Drop any Word or PDF file at [hiddenink.io](https://hiddenink.io) to see every hidden word highlighted and download a clean copy. Files are deleted after an hour and never sent to an AI.

![The Hidden Ink website](images/website.png)

## What runs on your computer

- **Your documents are never uploaded.** Every scan runs on your computer. The plugin makes no network calls of its own.
- **One download on first use.** `uv` downloads Python (if needed) and the libraries pinned in `uv.lock` from PyPI, about 100 MB. After that, nothing is downloaded. Some firm-managed laptops block this; ask IT to allow `uv` and PyPI.
- **The tools.** A small launcher (`server/launch.py`, Python's standard library only) answers Claude Code right away, then runs the scanner on this computer for each tool call.
- **The guard.** A Claude Code hook (`hooks/guard.sh`) reads each Read or Bash tool call that mentions a .docx or .pdf file, scans the files it names and replies to Claude Code. Other tool calls pass through untouched in a few milliseconds.
- **A local cache.** Results are kept for 30 days in your user cache folder (`~/Library/Caches/hiddenink` on a Mac), keyed by a SHA-256 fingerprint of the file. The cache holds findings only, never the document's text.
- **Safety limits.** Each scan runs in a separate process with a time limit. Files up to 2 GB are accepted.

The guard covers the normal ways Claude Code opens these files. It is a safety net, not a guarantee.

## Legal

Hidden Ink reports hidden content found by automated analysis. It is not legal advice. Hidden Ink is not affiliated with Anthropic.

Copyright Muna Omar. Licensed under the PolyForm Shield License 1.0.0 (see LICENSE): you may use Hidden Ink freely, but not to build a product that competes with it.
