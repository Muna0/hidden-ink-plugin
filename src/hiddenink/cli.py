"""hiddenink command-line tool."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import HiddenInkError
from .outputs.bundle import write_bundle
from .outputs.report import has_alarms, to_text
from .scan import scan_file


def _write_outputs(src: Path, result, out: Path) -> None:
    write_bundle(src, result, out, src.stem, preview=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hiddenink",
                                     description="Find hidden text in documents that AI can read but people cannot see.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Scan .docx and .pdf files")
    scan.add_argument("files", nargs="+", type=Path)
    scan.add_argument("--json", action="store_true", help="Print results as JSON")
    scan.add_argument("--out", type=Path, help="Write report, certificate, clean text, and cleaned copy here")
    serve = sub.add_parser("serve", help="Run the Hidden Ink web app and API on this computer")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("guard", help="Claude Code hook: read a PreToolUse event on stdin")
    sub.add_parser("mcp", help="Run the Hidden Ink MCP server over stdio")
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        print(f"Hidden Ink is running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
        uvicorn.run("hiddenink.api:create_app", factory=True, host=args.host, port=args.port,
                    log_level="warning", access_log=False)
        return 0

    if args.command == "guard":
        from .guard import run_hook

        out = run_hook(sys.stdin.read())
        if out:
            print(out)
        return 0

    if args.command == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()
        return 0

    errored = alarmed = False
    results = []
    for path in args.files:
        try:
            result = scan_file(path)
        except HiddenInkError as exc:
            print(f"{path.name}: error: {exc}", file=sys.stderr)
            errored = True
            continue
        alarmed = alarmed or has_alarms(result)
        results.append(result)
        if args.out:
            _write_outputs(path, result, args.out)
        if not args.json:
            print(to_text(result))
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
    return 1 if errored else 2 if alarmed else 0


if __name__ == "__main__":
    sys.exit(main())
