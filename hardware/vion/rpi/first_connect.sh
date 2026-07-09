#!/usr/bin/env bash
# First SSH session on Vion Raspberry Pi companion (delegates to pi_field_ready.sh).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/pi_field_ready.sh" --first-time "$@"
