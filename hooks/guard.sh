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

# First use: uv downloads Python and the libraries (about 2 minutes on a new computer), longer than
# Claude Code waits for a hook. Set up in the background and block documents until it is done, so no
# file is read unchecked.
ready="$root/.venv/.hiddenink-ready"
lock="$root/.setup-lock"
if [ ! -f "$ready" ]; then
  [ -d "$lock" ] && [ -n "$(find "$lock" -maxdepth 0 -mmin +10 2>/dev/null)" ] && rmdir "$lock" 2>/dev/null
  if mkdir "$lock" 2>/dev/null; then
    nohup sh -c '"$1" sync --locked --quiet --project "$2" && mkdir -p "${3%/*}" && touch "$3"; rmdir "$4"' sh \
      "$uv_bin" "$root" "$ready" "$lock" >/dev/null 2>&1 &
  fi
  waited=0
  while [ ! -f "$ready" ] && [ "$waited" -lt "${HIDDENINK_SETUP_WAIT:-20}" ]; do sleep 1; waited=$((waited + 1)); done
  if [ ! -f "$ready" ]; then
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Hidden Ink is finishing its one-time setup, which takes about 2 minutes the first time. Until then it cannot check this file for hidden text, so it stopped this read. Tell the user, wait a minute, and try again."}}'
    exit 0
  fi
fi

printf '%s' "$input" | "$uv_bin" run --locked --quiet --project "$root" hiddenink guard
exit 0
