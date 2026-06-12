#!/usr/bin/env bash
# Every Pi session: activate venv and run quick sensor check.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
source .venv/bin/activate

CONN="${MAVLINK_CONN:-/dev/ttyAMA0}"
python hardware/vion/rpi/check_sensors.py --once --connection "$CONN"
