# Vion Hardware

Pixhawk 6C fire suppression drone with Raspberry Pi companion for Task 2 autonomy.

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

Extinguish accuracy uses Pi camera + ToF only. H-Flow is for platform stability indoors.

## Lua scripts

| Script | Purpose |
|--------|---------|
| `safety.lua` | Emergency RC switch to LAND/disarm |
| `payload.lua` | Water payload servo control |
| `arm.lua` | Arm helper |
| `stabilize.lua` | Stabilize mode helper |
| `throttle_two.lua` | Watchdog + emergency handling |

Load scripts per Mission Planner docs in `mission-planner/003-setup.md`.

## Software entry points

| Platform | Command |
|----------|---------|
| RPi (competition) | `python hardware/vion/rpi/run_mission.py --profile indoor` |
| GCS (dev/fallback) | `python missions/task2_vion_auto_extinguish.py` |
| GCS monitor | `python tools/mission_monitor.py` |
