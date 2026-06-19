#!/usr/bin/env bash
# Vion Raspberry Pi setup: venv, package install, UART enable hints.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "=== Vion RPi setup ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[cv]"

echo ""
echo "Pi system packages (run once with sudo if not installed):"
echo "  sudo apt update"
echo "  sudo apt install -y python3-picamera2"
echo "  sudo usermod -aG dialout \$USER   # MAVLink serial access; re-login after"

UART_NEEDS_ENABLE=0
for cfg in /boot/firmware/config.txt /boot/config.txt; do
  if [ -f "$cfg" ] && grep -q "^#enable_uart=1" "$cfg" 2>/dev/null; then
    UART_NEEDS_ENABLE=1
    echo "NOTE: enable UART in $cfg (enable_uart=1) for Pixhawk TELEM"
  fi
done
if [ "$UART_NEEDS_ENABLE" -eq 1 ]; then
  echo "  Or: sudo raspi-config -> Interface Options -> Serial Port -> hardware Yes, login No"
fi

if [ ! -f config/rpas_calibration.yaml ]; then
  if [ -f config/rpas_calibration.yaml.example ]; then
    cp config/rpas_calibration.yaml.example config/rpas_calibration.yaml
    echo "Created config/rpas_calibration.yaml from example"
  elif [ ! -f config/vion_calibration.yaml ] && [ -f config/vion_calibration.yaml.example ]; then
    cp config/vion_calibration.yaml.example config/vion_calibration.yaml
    echo "Created config/vion_calibration.yaml from example (legacy)"
  fi
fi

echo ""
echo "First-time Pi? Run: bash hardware/vion/rpi/first_connect.sh"
echo ""
echo "Every session:"
echo "  source .venv/bin/activate"
echo "  bash hardware/vion/rpi/session_start.sh"
echo ""
echo "ArduCam ToF (once):"
echo "  bash hardware/vion/rpi/install_arducam_tof.sh"
echo ""
echo "Before flight:"
echo "  python hardware/vion/rpi/capture_calibration_set.py --distance 2.0"
echo "  python tools/valiant.py calibrate validate   # on GCS after copying logs/calibration"
echo "  python hardware/vion/rpi/run_mission.py --profile indoor --sim"
echo "  python hardware/vion/rpi/run_mission.py --profile indoor"
echo ""
echo "Docs: docs/runbooks/vion-bringup.md"
