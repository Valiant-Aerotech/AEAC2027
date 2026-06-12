#!/usr/bin/env bash
# First SSH session on Vion Raspberry Pi companion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "=== Vion Pi first-connect bringup ==="
echo ""

echo "1. Running setup.sh..."
bash hardware/vion/rpi/setup.sh

echo ""
echo "2. Checking UART..."
UART_OK=0
for cfg in /boot/firmware/config.txt /boot/config.txt; do
  if [ -f "$cfg" ] && grep -q "^enable_uart=1" "$cfg" 2>/dev/null; then
    UART_OK=1
    echo "   OK: enable_uart=1 in $cfg"
  fi
done
if [ "$UART_OK" -eq 0 ]; then
  echo "   WARN: enable_uart=1 not found."
  echo "   Run: sudo raspi-config -> Interface Options -> Serial Port -> hardware Yes, login No"
  echo "   Then reboot before MAVLink tests."
fi

echo ""
echo "3. Checking required files..."
MISSING=0
for f in models/best.onnx config/vion_calibration.yaml; do
  if [ -f "$f" ]; then
    echo "   OK: $f"
  else
    echo "   MISSING: $f"
    MISSING=1
  fi
done
if [ "$MISSING" -eq 1 ]; then
  echo "   Copy from laptop: scp models/best.onnx <user>@<pi>:~/AEAC2027/models/"
fi

if ! python -c "import ArducamDepthCamera" 2>/dev/null; then
  echo "   WARN: ArducamDepthCamera not installed"
  echo "   Run: bash hardware/vion/rpi/install_arducam_tof.sh (reboot), then pip install ArducamDepthCamera"
fi

echo ""
echo "4. MAVLink device..."
if [ -e /dev/ttyAMA0 ]; then
  echo "   OK: /dev/ttyAMA0"
elif ls /dev/ttyUSB* 1>/dev/null 2>&1; then
  echo "   Found USB serial (use --connection /dev/ttyUSB0 if needed):"
  ls /dev/ttyUSB*
else
  echo "   WARN: no /dev/ttyAMA0 or /dev/ttyUSB* yet"
fi

echo ""
echo "5. Next commands (props off, FC powered):"
echo "   source .venv/bin/activate"
echo "   bash hardware/vion/rpi/session_start.sh"
echo "   bash hardware/vion/rpi/capture_all_calibration.sh"
echo "   GCS_IP=<laptop-ip> bash hardware/vion/rpi/run_bringup_tests.sh"
echo "   bash hardware/vion/rpi/preflight_indoor.sh   # before props on"
echo ""
echo "See docs/runbooks/vion-bringup.md for full checklist."
