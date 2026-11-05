#!/bin/sh
# Hidden Ink guard. Exits fast unless the tool call mentions a .docx or .pdf file.
input=$(cat)
printf '%s' "$input" | grep -qiE '\.(docx|pdf)' || exit 0

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -n "$HIDDENINK_PYTHON" ]; then
  printf '%s' "$input" | "$HIDDENINK_PYTHON" -m hiddenink.cli guard
  exit 0
fi

uv_bin=$(command -v uv 2>/dev/null)
[ -z "$uv_bin" ] && [ -x "$HOME/.local/bin/uv" ] && uv_bin="$HOME/.local/bin/uv"
[ -z "$uv_bin" ] && [ -x "$HOME/.cargo/bin/uv" ] && uv_bin="$HOME/.cargo/bin/uv"
if [ -z "$uv_bin" ]; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Hidden Ink could not check this file for hidden text because uv is not installed. Tell the user they can install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"}}'
  exit 0
fi

printf '%s' "$input" | "$uv_bin" run --locked --quiet --project "$root" hiddenink guard
exit 0
