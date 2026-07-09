# Vion Hardware

Pixhawk 6C fire suppression drone with Raspberry Pi companion for Task 2 autonomy.

**Fresh Pi OS:** [docs/runbooks/pi-fresh-install.md](../../docs/runbooks/pi-fresh-install.md)  
**Bringup:** [docs/runbooks/vion-bringup.md](../../docs/runbooks/vion-bringup.md)

## Contents

- `lua/` - onboard ArduPilot Lua scripts (safety, payload, arm, stabilize, throttle)
- `mission-planner/` - FC parameter and setup notes (incl. `SCR_ENABLE`, safety.lua install)
- `rpi/` - onboard companion scripts (primary flight entry)

**Before field flight:** `python tools\valiant.py gcs verify-safety` — see [003-setup.md](mission-planner/003-setup.md).

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

Vivi (Kakute H7) wiring: [../vivi/WIRING.md](../vivi/WIRING.md)

## Software entry points

| Platform | Command |
|----------|---------|
| GCS first connect | `.\tools\gcs\bringup_gcs.ps1` |
| **RPi primary** | `bash hardware/vion/rpi/pi_field_ready.sh --check` |
| RPi first-time setup | `bash hardware/vion/rpi/pi_field_ready.sh --first-time` |
| RPi indoor flight | `python hardware/vion/rpi/run_mission.py --profile indoor` |
| RPi field orbit | `bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <ip> --laps 1` |
| GCS monitor | `python tools/valiant.py gcs monitor` |

Load Lua scripts per [mission-planner/003-setup.md](mission-planner/003-setup.md). Run `python tools\valiant.py gcs verify-safety` before every outdoor / props-on session.
