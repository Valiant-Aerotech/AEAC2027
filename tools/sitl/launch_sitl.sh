#!/usr/bin/env bash
# Launch ArduPilot SITL inside WSL (ArduCopter).
# Prereq: ~/ardupilot cloned and built — see docs/runbooks/sitl-wsl.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"

install_empy_via_apt() {
  if ! command -v apt-get &>/dev/null; then
    return 1
  fi
  if dpkg -s python3-empy &>/dev/null; then
    return 0
  fi
  echo "Installing python3-empy via apt (Ubuntu 3.3.4)..."
  if sudo -n apt-get install -y python3-empy &>/dev/null; then
    return 0
  fi
  return 1
}

install_empy_via_pip() {
  if ! python3 -m pip --version &>/dev/null; then
    echo "ERROR: pip is not installed in WSL."
    echo "Run once in a WSL Ubuntu terminal:"
    echo "  sudo apt update && sudo apt install -y python3-empy"
    echo "Or: sudo apt install -y python3-pip && python3 -m pip install --user --break-system-packages empy==3.3.4"
    echo "Then retry from PowerShell: .\\tools\\launch_sitl.ps1"
    exit 1
  fi
  echo "Installing empy via pip (--break-system-packages; required on Ubuntu 24.04+)..."
  python3 -m pip install --user --break-system-packages -r "$SCRIPT_DIR/requirements-wsl.txt"
}

ensure_empy() {
  if python3 -c "import empy" 2>/dev/null; then
    return 0
  fi
  if install_empy_via_apt; then
    return 0
  fi
  install_empy_via_pip
  if ! python3 -c "import empy" 2>/dev/null; then
    echo "ERROR: empy still not available after install attempt."
    echo "Run once in a WSL Ubuntu terminal:"
    echo "  sudo apt update && sudo apt install -y python3-empy"
    exit 1
  fi
}

ensure_empy

if [[ ! -f "$ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py" ]]; then
  echo "ERROR: ArduPilot not found at $ARDUPILOT_DIR"
  echo "Clone: git clone https://github.com/ArduPilot/ardupilot.git ~/ardupilot"
  exit 1
fi

REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOME_JSON="${SITL_HOME_JSON:-$REPO_DIR/tests/fixtures/sitl_home.json}"
if [[ ! -f "$HOME_JSON" ]]; then
  echo "ERROR: SITL home file not found: $HOME_JSON"
  exit 1
fi
SITL_LOC="$(python3 -c "import json; h=json.load(open('${HOME_JSON}')); print(f\"{h['lat_deg']},{h['lon_deg']},{h['alt_m']},{h['heading_deg']}\")")"

cd "$ARDUPILOT_DIR"
echo "Starting ArduCopter SITL (TCP 5760, home=${SITL_LOC})..."
echo "Arm GUIDED from Windows: .\\tools\\run_sitl_mission.ps1 -Physics"
exec ./Tools/autotest/sim_vehicle.py -v ArduCopter --no-mavproxy -l "$SITL_LOC" "$@"
