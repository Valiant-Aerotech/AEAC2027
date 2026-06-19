#!/usr/bin/env bash
# Phase 1 Pi checks: RGB, optional ToF, MAVLink, calibration hint.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
source .venv/bin/activate

echo "=== Phase 1 Pi bringup ==="
python hardware/vion/rpi/check_sensors.py --once --profile indoor

CAL_DIR="$REPO_ROOT/logs/calibration"
if [ -d "$CAL_DIR/1m" ] && [ -d "$CAL_DIR/2m" ]; then
  echo ""
  echo "=== Depth calibration validation (10% gate) ==="
  python tools/valiant.py calibrate validate || {
    echo "WARN: calibration validation failed - re-run capture_all_calibration.sh"
    exit 1
  }
else
  echo ""
  echo "Depth calibration not captured yet."
  echo "  bash hardware/vion/rpi/capture_all_calibration.sh"
  echo "  Then on GCS: .\\tools\\run_calibration_pipeline.ps1 -PiHost user@ip"
fi

echo ""
echo "Phase 1 Pi checks complete. Next: run_bringup_tests.sh (sim/tethered)"
