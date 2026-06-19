# Telemetry and dual-link setup

## GCS telemetry radio

Download CP210x driver if needed: https://micoair.com/downloads/

- Baud rate: **57600**
- Connect Mission Planner to telemetry radio COM port
- Pi uses a **separate** Pixhawk TELEM port (UART) - do not share the same SERIAL port

## Pixhawk TELEM port for Pi

On the TELEM port wired to the Raspberry Pi:

- `SERIALx_PROTOCOL` = `2` (MAVLink2)
- `SERIALx_BAUD` = `57` (57600)

Pi default connection: `/dev/ttyAMA0` @ 57600.

## Pi UART enable

On Raspberry Pi:

- `enable_uart=1` in `/boot/firmware/config.txt` (or `/boot/config.txt`)
- Serial login shell disabled (`sudo raspi-config` -> Serial Port -> hardware Yes, login No)

## Bringup runbook

See [docs/runbooks/vion-bringup.md](../../../docs/runbooks/vion-bringup.md).

GCS first connect: `.\tools\gcs\bringup_gcs.ps1`

Pi TELEM + H-Flow params: [002-pi-telem-params.md](002-pi-telem-params.md)

## Onboard Lua scripts (safety)

Copy scripts from [`hardware/vion/lua/`](../../lua/) to the FC SD card under **`APM/scripts/`**:

| Script | Purpose |
|--------|---------|
| `safety.lua` | **Required for field flight** — kill switch RC8 → LAND |
| `payload.lua` | Spray servo cycling (bench) |
| `arm.lua`, `stabilize.lua` | Dev helpers |

Preflight: `python tools\valiant.py gcs verify-safety` (checks `SCR_ENABLE` and `scripts/safety.lua`).

Orbit / mission scripts on the Pi **refuse to start** if this check fails (`safety.require_lua_safety: true` in `config/vion.yaml`).
