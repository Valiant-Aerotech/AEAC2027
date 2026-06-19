#!/usr/bin/env bash
# One-time ArduPilot SITL setup inside WSL Ubuntu (idempotent).
# Invoked from Windows: .\tools\setup_wsl.ps1
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
MARKER="$HOME/.valiant_ardupilot_sitl_built"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

apt_install_if_available() {
  local pkg="$1"
  if apt-cache show "$pkg" &>/dev/null; then
    sudo apt-get install -y "$pkg"
  else
    echo "  SKIP (not in apt on this Ubuntu): $pkg"
  fi
}

pip_install_user() {
  local pkg="$1"
  if python3 -c "import ${pkg//-/_}" 2>/dev/null; then
    return 0
  fi
  if python3 -m pip install --user --break-system-packages "$pkg" 2>/dev/null; then
    return 0
  fi
  python3 -m pip install --user "$pkg"
}

echo "=== Valiant SITL / WSL setup (inside Ubuntu) ==="
echo "ArduPilot dir: $ARDUPILOT_DIR"
echo ""

echo "[1/4] System packages..."
sudo apt-get update -qq
sudo apt-get install -y \
  git python3 python3-pip python3-dev python3-empy python3-venv \
  build-essential ccache g++ gawk wget curl \
  libxml2-dev libxslt1-dev zlib1g-dev libffi-dev

# Optional on older Ubuntu; Noble (24.04) drops some python3-* apt packages
for pkg in python3-lxml python3-future python3-pexpect; do
  apt_install_if_available "$pkg" || true
done

# Pip fallback for Noble / missing apt packages (needed by pymavlink/waf)
for pkg in future pexpect lxml; do
  pip_install_user "$pkg" || echo "  WARN: pip install $pkg failed (install-prereqs may fix)"
done

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
  if ! Tools/environment_install/install-prereqs-ubuntu.sh -y; then
    echo "WARN: install-prereqs-ubuntu.sh returned non-zero; trying pip fallbacks..."
    pip_install_user future || true
    pip_install_user pexpect || true
    pip_install_user setuptools || true
  fi
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
