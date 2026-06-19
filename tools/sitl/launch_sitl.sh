#!/usr/bin/env bash
# Launch ArduPilot SITL inside WSL (ArduCopter).
# Prereq: ~/ardupilot cloned and built - see docs/runbooks/sitl-wsl.md
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$_SCRIPT_DIR/common.sh"
trap valiant_on_err ERR

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"

install_empy_via_apt() {
  if ! command -v apt-get &>/dev/null; then
    return 1
  fi
  if dpkg -s python3-empy &>/dev/null; then
    return 0
  fi
  valiant_log "Installing python3-empy via apt (Ubuntu 3.3.4)..."
  if sudo -n apt-get install -y python3-empy &>/dev/null; then
    return 0
  fi
  return 1
}

install_empy_via_pip() {
  if ! python3 -m pip --version &>/dev/null; then
    valiant_die "pip is not installed in WSL" \
      "sudo apt update && sudo apt install -y python3-empy" \
      "Or: sudo apt install -y python3-pip && python3 -m pip install --user --break-system-packages empy==3.3.4" \
      "Then: .\\tools\\launch_sitl.ps1"
  fi
  valiant_log "Installing empy via pip (--break-system-packages)..."
  python3 -m pip install --user --break-system-packages -r "$_SCRIPT_DIR/requirements-wsl.txt"
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
    valiant_die "empy still not available after install" \
      "source ~/venv-ardupilot/bin/activate" \
      "sudo apt install -y python3-empy"
  fi
}

ensure_empy

valiant_require_file "$ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py" "ArduPilot sim_vehicle.py" \
  "Run: .\\tools\\setup_wsl.ps1"

REPO_DIR="$(cd "$_SCRIPT_DIR/../.." && pwd)"
HOME_JSON="${SITL_HOME_JSON:-$REPO_DIR/tests/fixtures/sitl_home.json}"
valiant_require_file "$HOME_JSON" "SITL home JSON" \
  "Expected: tests/fixtures/sitl_home.json in repo"

SITL_LOC="$(python3 -c "import json; h=json.load(open('${HOME_JSON}')); print(f\"{h['lat_deg']},{h['lon_deg']},{h['alt_m']},{h['heading_deg']}\")")" \
  || valiant_die "Invalid SITL home JSON: $HOME_JSON"

cd "$ARDUPILOT_DIR"
valiant_log "Starting ArduCopter SITL (TCP 5760, home=${SITL_LOC})..."
valiant_log "Arm GUIDED from Windows: .\\tools\\run_sitl_mission.ps1"
exec ./Tools/autotest/sim_vehicle.py -v ArduCopter --no-mavproxy -l "$SITL_LOC" "$@"
