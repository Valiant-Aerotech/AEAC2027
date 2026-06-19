#!/usr/bin/env bash
# Install Arducam ToF SDK on Raspberry Pi (system-level, requires reboot).
set -euo pipefail

echo "=== Arducam ToF SDK install ==="
echo ""
echo "This clones ArduCAM/Arducam_tof_camera and runs Install_dependencies.sh."
echo "A reboot is required after install."
echo ""

REPO_DIR="${HOME}/Arducam_tof_camera"
if [ ! -d "$REPO_DIR" ]; then
  git clone https://github.com/ArduCAM/Arducam_tof_camera.git "$REPO_DIR"
fi

cd "$REPO_DIR"
chmod +x Install_dependencies.sh compile.sh 2>/dev/null || true

echo "Running Install_dependencies.sh (may prompt for reboot)..."
./Install_dependencies.sh

echo ""
echo "Compiling examples..."
./compile.sh || echo "WARN: compile.sh failed - SDK may still work via pip wheel"

echo ""
echo "Install Python package into AEAC2027 venv:"
AEAC_DIR="${AEAC2027_ROOT:-$HOME/AEAC2027}"
if [ -d "$AEAC_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$AEAC_DIR/.venv/bin/activate"
  pip install -q ArducamDepthCamera || echo "WARN: pip install ArducamDepthCamera failed"
  echo "Installed ArducamDepthCamera into $AEAC_DIR/.venv"
else
  echo "  cd ~/AEAC2027 && source .venv/bin/activate"
  echo "  pip install ArducamDepthCamera"
fi
echo ""
echo "On 64-bit Pi OS, if pip installs wrong arch wheel, build from source:"
echo "  see https://docs.arducam.com/Raspberry-Pi-Camera/Tof-camera/"
echo ""
echo "Reboot, then test:"
echo "  python hardware/vion/rpi/check_sensors.py"
