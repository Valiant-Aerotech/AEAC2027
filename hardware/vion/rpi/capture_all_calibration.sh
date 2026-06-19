#!/usr/bin/env bash
# Capture calibration RGB+depth at 1 m, 2 m, 3 m (bringup Phase C6).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
source .venv/bin/activate

for dist in 1.0 2.0 3.0; do
  echo "=== Capture at ${dist}m - place target at tape distance, press Enter ==="
  read -r
  python hardware/vion/rpi/capture_calibration_set.py --distance "$dist"
done

echo ""
echo "Done. Copy logs/calibration to GCS:"
echo "  scp -r <pi>:~/AEAC2027/logs/calibration ./logs/"
echo "Then on GCS: python tools/valiant.py calibrate validate"
