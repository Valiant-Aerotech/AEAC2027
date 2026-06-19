#!/usr/bin/env bash
# One-time ArduPilot SITL setup inside WSL Ubuntu (idempotent).
# Invoked from Windows: .\tools\setup_wsl.ps1
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
MARKER="$HOME/.valiant_ardupilot_sitl_built"
PREREQS_MARKER="$HOME/.valiant_ardupilot_prereqs_done"
BUILD_LOG="$HOME/.valiant_sitl_build.log"
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

prereqs_ok() {
  local py
  for py in \
    "$HOME/venv-ardupilot/bin/python" \
    "$ARDUPILOT_DIR/venv-ardupilot/bin/python" \
    "$ARDUPILOT_DIR/.venv/bin/python"; do
    if [[ -x "$py" ]] && "$py" -c "import empy" 2>/dev/null; then
      return 0
    fi
  done
  if python3 -c "import empy" 2>/dev/null; then
    return 0
  fi
  return 1
}

activate_ardupilot_venv() {
  local activate
  for activate in \
    "$HOME/venv-ardupilot/bin/activate" \
    "$ARDUPILOT_DIR/venv-ardupilot/bin/activate" \
    "$ARDUPILOT_DIR/.venv/bin/activate"; do
    if [[ -f "$activate" ]]; then
      # shellcheck disable=SC1090
      set +u
      source "$activate"
      set -u
      echo "  Using venv: $(dirname "$(dirname "$activate")")"
      return 0
    fi
  done
  echo "  WARN: no ArduPilot venv found; using system python3"
  return 0
}

waf_jobs() {
  local n
  n="$(nproc 2>/dev/null || echo 4)"
  if [[ "$n" -gt 4 ]]; then
    n=4
  fi
  if [[ "$n" -lt 1 ]]; then
    n=1
  fi
  echo "$n"
}

print_build_failure() {
  echo ""
  echo "ERROR: ArduCopter SITL build failed."
  echo "Full log: $BUILD_LOG"
  if [[ -f "$BUILD_LOG" ]]; then
    echo ""
    echo "--- last 40 lines of build log ---"
    tail -40 "$BUILD_LOG" || true
    echo "--- end ---"
  fi
  echo ""
  echo "Recovery (in Ubuntu):"
  echo "  source ~/venv-ardupilot/bin/activate"
  echo "  cd ~/ardupilot"
  echo "  ./waf configure --board sitl"
  echo "  ./waf copter -j$(waf_jobs)"
  echo ""
  echo "Or re-run from Windows (skips completed steps):"
  echo "  .\\tools\\setup_wsl.ps1"
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
echo "[3/4] ArduPilot Linux prereqs (SITL-only; may take several minutes on first run)..."
if [[ ! -f "$PREREQS_MARKER" ]]; then
  # SITL-only: skip STM32 toolchain, venv prompt, completion, and redundant submodule pass
  export DO_AP_STM_ENV=0
  export DO_PYTHON_VENV_ENV=1
  export SKIP_AP_COMPLETION_ENV=1
  export SKIP_AP_GIT_CHECK=1

  prereqs_rc=0
  if ! Tools/environment_install/install-prereqs-ubuntu.sh -y; then
    prereqs_rc=$?
    echo "WARN: install-prereqs-ubuntu.sh returned $prereqs_rc; trying pip fallbacks..."
    pip_install_user future || true
    pip_install_user pexpect || true
    pip_install_user setuptools || true
  fi

  if [[ "$prereqs_rc" -eq 0 ]] || prereqs_ok; then
    touch "$PREREQS_MARKER"
  else
    echo "ERROR: ArduPilot prereqs incomplete (empy/venv missing). See log above."
    exit 1
  fi
else
  echo "  Skipping (marker $PREREQS_MARKER exists)"
fi

# install-prereqs updates ~/.profile; load paths for waf
if [[ -f "$HOME/.profile" ]]; then
  # shellcheck disable=SC1090
  set +u
  source "$HOME/.profile" 2>/dev/null || true
  set -u
fi

activate_ardupilot_venv

echo ""
echo "[4/4] Build ArduCopter SITL (first run can take 10-20 min)..."
if [[ -f "$MARKER" ]] && [[ -f "$ARDUPILOT_DIR/build/sitl/bin/arducopter" ]]; then
  echo "  Skipping build (already built; delete $MARKER to force rebuild)"
else
  jobs="$(waf_jobs)"
  echo "  Build log: $BUILD_LOG"
  : >"$BUILD_LOG"
  set +e
  {
    echo "=== waf configure $(date -Iseconds) ==="
    ./waf configure --board sitl
  } 2>&1 | tee -a "$BUILD_LOG"
  build_rc=${PIPESTATUS[0]}
  if [[ "$build_rc" -eq 0 ]]; then
    {
      echo "=== waf copter -j$jobs $(date -Iseconds) ==="
      ./waf copter -j"$jobs"
      echo "=== waf copter exit: $? ==="
    } 2>&1 | tee -a "$BUILD_LOG"
    build_rc=${PIPESTATUS[0]}
  else
    echo "=== waf configure exit: $build_rc ===" | tee -a "$BUILD_LOG"
  fi
  set -e
  if [[ "$build_rc" -ne 0 ]] || [[ ! -f "$ARDUPILOT_DIR/build/sitl/bin/arducopter" ]]; then
    print_build_failure
    exit "${build_rc:-1}"
  fi
  touch "$MARKER"
fi

echo ""
echo "=== WSL SITL setup complete ==="
echo "From Windows repo root:"
echo "  Terminal 1:  .\\tools\\launch_sitl.ps1"
echo "  Terminal 2:  python tools\\valiant.py sitl mission"
echo ""
