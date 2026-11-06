# Hidden Ink Check

Hidden Ink Check, created by Muna Omar, looks for text in Word (.docx) and PDF files that an AI can read but a person cannot see. Hidden text can tell an AI to skip a clause, praise a document or change its summary. In July 2025, reporters found hidden AI instructions in research papers from 14 universities; the same tricks work in contracts, court filings and résumés.

Before Claude reads a Word or PDF file, this skill has Claude run a short check and tell you what it found, where, and a quote of it. Claude is told never to follow hidden text.

## Install

In Claude Code:

```
/plugin marketplace add Muna0/hidden-ink-plugin
/plugin install hidden-ink-check@hidden-ink
```

It also works in Claude apps that support skills, where Claude runs the check in its own sandbox on files you upload.

## What it checks

**Word (.docx):** hidden Word text (including hidden styles), text the same color as its background, tiny fonts, text boxes placed off the page, field codes, alt text, comments and tracked deletions addressed to an AI, document properties, and invisible Unicode characters.

**PDF:** invisible text (render mode 3), white or same-color text, tiny text, text off the page, text covered by a shape, annotations and document properties addressed to an AI, and invisible Unicode characters.

To keep false alarms low, hidden text is reported only when it says something: at least four words, or an instruction to an AI. Stray hidden page numbers, punctuation and printer's marks, which are common in ordinary documents, are not reported. Comments, alt text and document properties are reported only when they give an AI instructions, not when they merely mention AI.

On Hidden Ink's published test set it catches 22 of 22 hiding tricks with 0 false alarms on 13 ordinary documents, including Somali and Persian text, redlines and fine print.

## What runs on your computer

- The skill contains one Python script, written out in full in `skills/hidden-ink-check/SKILL.md` so you can read every line.
- Claude saves it to a temporary file and runs it with Python 3. Claude Code asks your permission first.
- It uses only the Python standard library. It reads the file you are checking, makes no network calls, writes nothing and installs nothing.
- Nothing is sent to Hidden Ink.

## Limits

This is a lighter version of Hidden Ink. It can miss text in unusual PDF encodings, images and embedded files. For the full scanner, which runs on your computer and checks every Word and PDF file before Claude reads it, see [hiddenink.io](https://hiddenink.io).

"No hidden text found" never means a file is safe; it means these checks found nothing.

## Privacy, terms and support

[Privacy policy](https://hiddenink.io/privacy/) · [Terms of service](https://hiddenink.io/terms/) · [Support](https://hiddenink.io/support/)

## License

PolyForm Shield 1.0.0. See LICENSE.

Hidden Ink Check reports hidden content found by automated analysis. It is not legal advice.
