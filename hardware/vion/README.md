# Vion Hardware

Pixhawk 6C fire suppression drone. No companion computer - GCS laptop runs autonomy.

## Contents

- `mission-planner/` - FC parameter docs and telemetry setup
- `lua/` - onboard ArduPilot Lua scripts (safety, payload, arm)

## Key parameters

- Water trigger: AUX 7 / SERVO15
- Rangefinder: VL53L1X on I2C
- `SCR_ENABLE = 1` for Lua scripting

## Migration

Lua scripts will be copied from `old-codebase/actuation/lua/` in Track B7.
