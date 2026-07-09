#!/usr/bin/env bash
# Session prep on Pi: venv + sensor/MAVLink check (delegates to pi_field_ready.sh).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/pi_field_ready.sh" --check "$@"
