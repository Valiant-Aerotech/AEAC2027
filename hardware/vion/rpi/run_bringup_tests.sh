#!/usr/bin/env bash
# Sim + tethered bringup tests (Phase C7-C8, D). Props off for tethered.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
source .venv/bin/activate

CONN="${MAVLINK_CONN:-/dev/ttyAMA0}"
GCS_IP="${GCS_IP:-}"

echo "=== Phase C7: Sim mission (no velocity commands) ==="
python hardware/vion/rpi/run_mission.py --profile indoor --sim --max-targets 1
echo "PASS if state machine advanced with target in view."

echo ""
echo "=== Phase C8: Tethered live (props OFF, hold airframe) ==="
echo "Confirm Mission Planner shows GUIDED_NOGPS and T2: STATUSTEXT."
read -r -p "Press Enter to start tethered test (Ctrl+C aborts)..."
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1 --connection "$CONN"
echo "PASS if Ctrl+C zeroed velocity."

if [ -n "$GCS_IP" ]; then
  echo ""
  echo "=== Phase D: WiFi monitor test ==="
  echo "On GCS run: python tools/mission_monitor.py"
  read -r -p "Press Enter to start sim with GCS mirror to $GCS_IP..."
  python hardware/vion/rpi/run_mission.py --profile indoor --sim \
    --gcs-connection "udpout:${GCS_IP}:14550"
fi

echo ""
echo "Bringup tests complete. See docs/runbooks/vion-bringup.md Phase E for props-on flight."
