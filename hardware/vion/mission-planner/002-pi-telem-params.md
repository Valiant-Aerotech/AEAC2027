# Pi TELEM port + H-Flow DroneCAN parameters for first-time bringup.

Set these in Mission Planner on the **TELEM port wired to the Raspberry Pi**.
The GCS telemetry radio must use a **different** SERIAL port.

## Pi companion UART (TELEM port)

Replace `x` with the port number (e.g. TELEM1 = SERIAL1, TELEM2 = SERIAL2).

| Parameter | Value | Notes |
|-----------|-------|-------|
| `SERIALx_PROTOCOL` | `2` | MAVLink2 |
| `SERIALx_BAUD` | `57` | 57600 baud |
| `SERIALx_OPTIONS` | `0` | Default unless you need inversion |

Pi software default: `/dev/ttyAMA0` @ 57600.

## Holybro H-Flow (DroneCAN)

See also [001-parameters.md](001-parameters.md).

| Parameter | Value |
|-----------|-------|
| `FLOW_TYPE` | `6` |
| `RNGFND1_TYPE` | `24` |
| `FLOW_POS_X` | mount offset (m) |
| `FLOW_POS_Y` | mount offset (m) |
| `FLOW_POS_Z` | mount offset (m) |
| `RNGFND1_POS_X` | same bore-sight as flow |
| `RNGFND1_POS_Y` | same |
| `RNGFND1_POS_Z` | same |

Verify H-Flow appears in Mission Planner DroneCAN / status view.

## Indoor profile

- `GUIDED_NOGPS` available in mode list
- Geofence relaxed or disabled for indoor runs (Pi sets `geofence_abort: false` for indoor)

## Bench pass criteria

- [ ] Pi TELEM params saved and rebooted
- [ ] H-Flow visible on CAN bus
- [ ] `opt_qua` > ~100 on venue-like flooring at 0.5-3 m AGL (hover test)
- [ ] Pi `check_sensors.py` gets MAVLink heartbeat on `/dev/ttyAMA0`

Print quick reference: `.\tools\bringup\print_fc_params.ps1`
