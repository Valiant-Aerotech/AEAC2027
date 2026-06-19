#!/usr/bin/env bash
# Run a repo bash script from Windows: strip CRLF, tee to log, preserve exit code.
# Usage: wsl_run.sh <script.sh> <log-file> [args...]
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: wsl_run.sh <script.sh> <log-file> [args...]" >&2
  exit 2
fi

SCRIPT="$1"
LOG="$2"
shift 2

SCRIPT_DIR="$(cd "$(dirname "$SCRIPT")" && pwd)"
export VALIANT_SITL_SCRIPT_DIR="$SCRIPT_DIR"

TMP="$(mktemp)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

sed 's/\r$//' "$SCRIPT" > "$TMP"
chmod +x "$TMP"
bash "$TMP" "$@" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
