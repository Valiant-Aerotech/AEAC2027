# Vion Hardware

Pixhawk 6C fire suppression drone with Raspberry Pi companion for Task 2 autonomy.

**First-time bringup:** [docs/runbooks/vion-bringup.md](../../docs/runbooks/vion-bringup.md)

## Contents

- `lua/` - onboard ArduPilot Lua scripts (safety, payload, arm, stabilize, throttle)
- `mission-planner/` - FC parameter and setup notes
- `rpi/` - onboard companion scripts (primary flight entry)

## Sensor stack

| Sensor | Role |
|--------|------|
| Holybro H-Flow (DroneCAN, downward) | Indoor optical flow + FC altitude (EKF) |
| RPi AI camera | YOLO target detection |
| ArduCam ToF (on Pi) | Target distance (`depth_at_target`) |

## Dual MAVLink links

| Link | Purpose |
|------|---------|
| GCS telemetry radio -> Pixhawk | Mission Planner, params, spray test, H-Flow bench |
| Pi UART -> Pixhawk TELEM | Autonomous mission control |
| Pi WiFi -> GCS UDP | Read-only monitor |

## Software entry points

| Platform | Command |
|----------|---------|
| GCS first connect | `.\tools\gcs\bringup_gcs.ps1` |
| RPi first SSH | `bash hardware/vion/rpi/first_connect.sh` |
| RPi flight | `python hardware/vion/rpi/run_mission.py --profile indoor` |
| GCS monitor | `python tools/valiant.py gcs monitor` |
| GCS dev fallback | `python missions/task2_vion_auto_extinguish.py` |

Load Lua scripts per [mission-planner/003-setup.md](mission-planner/003-setup.md).
