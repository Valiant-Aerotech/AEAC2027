#!/usr/bin/env bash
# Launch ArduPilot SITL inside WSL (ArduCopter).
# Prereq: ~/ardupilot cloned and built — see docs/runbooks/sitl-wsl.md
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
if [[ ! -f "$ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py" ]]; then
  echo "ERROR: ArduPilot not found at $ARDUPILOT_DIR"
  echo "Clone: git clone https://github.com/ArduPilot/ardupilot.git ~/ardupilot"
  exit 1
fi

cd "$ARDUPILOT_DIR"
echo "Starting ArduCopter SITL (TCP 5760 on localhost)..."
exec ./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map "$@"
