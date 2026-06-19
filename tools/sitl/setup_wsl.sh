#!/usr/bin/env bash
# One-time ArduPilot SITL setup inside WSL Ubuntu (idempotent).
# Invoked from Windows: .\tools\setup_wsl.ps1
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
MARKER="$HOME/.valiant_ardupilot_sitl_built"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Valiant SITL / WSL setup (inside Ubuntu) ==="
echo "ArduPilot dir: $ARDUPILOT_DIR"
echo ""

echo "[1/4] System packages..."
sudo apt-get update -qq
sudo apt-get install -y git python3 python3-pip python3-dev python3-empy \
  build-essential ccache g++ gawk wget curl \
  libxml2-dev libxslt1-dev python3-lxml python3-future python3-pexpect \
  zlib1g-dev libffi-dev

echo ""
echo "[2/4] ArduPilot source..."
if [[ ! -d "$ARDUPILOT_DIR/.git" ]]; then
  git clone --depth 1 --recurse-submodules \
    https://github.com/ArduPilot/ardupilot.git "$ARDUPILOT_DIR"
else
  echo "  Already cloned at $ARDUPILOT_DIR"
fi

cd "$ARDUPILOT_DIR"
if [[ ! -f Tools/environment_install/install-prereqs-ubuntu.sh ]]; then
  echo "ERROR: install-prereqs-ubuntu.sh not found in $ARDUPILOT_DIR"
  exit 1
fi

echo ""
echo "[3/4] ArduPilot Linux prereqs (may take several minutes on first run)..."
if [[ ! -f "$HOME/.valiant_ardupilot_prereqs_done" ]]; then
  Tools/environment_install/install-prereqs-ubuntu.sh -y
  touch "$HOME/.valiant_ardupilot_prereqs_done"
else
  echo "  Skipping (marker $HOME/.valiant_ardupilot_prereqs_done exists)"
fi

# install-prereqs updates ~/.profile; load paths for waf
if [[ -f "$HOME/.profile" ]]; then
  # shellcheck disable=SC1090
  set +u
  source "$HOME/.profile" 2>/dev/null || true
  set -u
fi

echo ""
echo "[4/4] Build ArduCopter SITL (first run can take 10-20 min)..."
if [[ -f "$MARKER" ]] && [[ -f "$ARDUPILOT_DIR/build/sitl/bin/arducopter" ]]; then
  echo "  Skipping build (already built; delete $MARKER to force rebuild)"
else
  ./waf configure --board sitl
  ./waf copter
  touch "$MARKER"
fi

echo ""
echo "=== WSL SITL setup complete ==="
echo "From Windows repo root:"
echo "  Terminal 1:  .\\tools\\launch_sitl.ps1"
echo "  Terminal 2:  python tools\\valiant.py sitl mission"
echo ""
