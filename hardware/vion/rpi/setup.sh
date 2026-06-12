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

if grep -q "^#enable_uart=1" /boot/firmware/config.txt 2>/dev/null; then
  echo "NOTE: enable UART in /boot/firmware/config.txt (enable_uart=1) for Pixhawk TELEM"
elif grep -q "^#enable_uart=1" /boot/config.txt 2>/dev/null; then
  echo "NOTE: enable UART in /boot/config.txt (enable_uart=1) for Pixhawk TELEM"
fi

if [ ! -f config/vion_calibration.yaml ]; then
  cp config/vion_calibration.yaml.example config/vion_calibration.yaml
  echo "Created config/vion_calibration.yaml from example"
fi

echo ""
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  python hardware/vion/rpi/check_sensors.py"
echo "  python hardware/vion/rpi/capture_calibration_set.py --distance 2.0"
echo "  python tools/validate_calibration.py"
echo "  python hardware/vion/rpi/run_mission.py --profile indoor --sim"
