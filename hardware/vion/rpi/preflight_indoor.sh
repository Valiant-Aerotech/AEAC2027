#!/usr/bin/env bash
# Pre-flight checklist before props-on indoor flight (Phase E).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

FAIL=0

check() {
  if "$@"; then
    echo "  OK: $*"
  else
    echo "  FAIL: $*"
    FAIL=1
  fi
}

echo "=== Vion indoor preflight (props ON) ==="
echo "Spotter and RC override required. Abort if any FAIL."
echo ""

echo "1. Software on Pi..."
source .venv/bin/activate
check test -f models/best.onnx
check test -f config/rpas_calibration.yaml -o -f config/vion_calibration.yaml

echo ""
echo "2. Sensors + MAVLink + safety.lua..."
CONN="${MAVLINK_CONN:-/dev/ttyAMA0}"
check python hardware/vion/rpi/check_sensors.py --once --connection "$CONN"

echo ""
echo "3. Manual checks (confirm on GCS / physically):"
echo "   [ ] Mission Planner heartbeat via telemetry radio"
echo "   [ ] H-Flow opt_qua OK on venue-like floor (hover)"
echo "   [ ] Messages shows 'safety: kill monitor loaded (RC8)' after FC reboot"
echo "   [ ] Emergency RC switch tested (flip -> LAND in Messages)"
echo "   [ ] Water tank filled"
echo "   [ ] GCS python tools/valiant.py gcs monitor running (optional)"
echo ""
read -r -p "Type YES if all manual checks done: " confirm
if [ "$confirm" != "YES" ]; then
  echo "Aborted."
  exit 1
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo "FAIL: fix automated checks before flight."
  exit 1
fi

echo ""
echo "Ready. Run:"
echo "  python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1"
if [ -n "${GCS_IP:-}" ]; then
  echo "  --gcs-connection udpout:${GCS_IP}:14550"
fi
