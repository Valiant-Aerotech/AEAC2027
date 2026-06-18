#!/usr/bin/env bash
# Session prep on Pi: venv, optional MAVLink check.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
source .venv/bin/activate
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
python hardware/vion/rpi/check_sensors.py --profile vivi --once "$@"
