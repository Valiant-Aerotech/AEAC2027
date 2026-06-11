# Vion Hardware

Pixhawk 6C fire suppression drone. GCS laptop runs Task 2 autonomy via scrcpy + MAVLink.

## Contents

- `lua/` - onboard ArduPilot Lua scripts (safety, payload, arm, stabilize, throttle)
- `mission-planner/` - FC parameter and setup notes

## Lua scripts

| Script | Purpose |
|--------|---------|
| `safety.lua` | Emergency RC switch to LAND/disarm |
| `payload.lua` | Water payload servo control |
| `arm.lua` | Arm helper |
| `stabilize.lua` | Stabilize mode helper |
| `throttle_two.lua` | Watchdog + emergency handling |

Load scripts per Mission Planner docs in `mission-planner/003-setup.md`.
