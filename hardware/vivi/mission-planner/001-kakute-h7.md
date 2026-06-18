# Kakute H7 — Vivi Mission Planner parameters

Vivi uses a **Holybro Kakute H7** running **ArduPilot** (required — Betaflight/iNav will not work with this stack).

## Dual MAVLink links

| Link | Physical | Mission Planner |
|------|----------|-----------------|
| **GCS telemetry** | USB or TELEM radio | Connect laptop @ **57600** — pilot view, arm, params |
| **Pi companion** | Pi UART → dedicated FC UART | **Not** the GCS port — Pi runs autonomy |

Identify which `SERIALx` port is wired to the Pi in **Setup → Full Parameter List** (or Serial Ports tab). Example if Pi is on UART4:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `SERIAL4_PROTOCOL` | `2` | MAVLink2 |
| `SERIAL4_BAUD` | `57` | 57600 baud |
| `SERIAL4_OPTIONS` | `0` | Default |

Repeat for the GCS radio port (often `SERIAL1` or USB `SERIAL0`) — **different** from the Pi port.

## Pi companion

- Pi connects at `/dev/ttyAMA0` @ 57600 ([`config/vion.yaml`](../../../config/vion.yaml) `mavlink.rpi_connection`)
- Companion uses MAVLink component **191** for `T2:` HUD statustext

## Pitch camera gimbal servo

The gimbal uses one AUX servo channel (set in `flight_profiles.vivi` → `gimbal.channel`).

| Parameter | Value | Notes |
|-----------|-------|-------|
| `SERVOn_FUNCTION` | `0` | Disabled / manual — allows `MAV_CMD_DO_SET_SERVO` from Pi |
| `SERVOn_MIN` | `1000` | Match `gimbal.pwm_min` in yaml (tune on bench) |
| `SERVOn_MAX` | `2000` | Match `gimbal.pwm_max` in yaml |
| `SERVOn_TRIM` | `1500` | Neutral / mid pitch |

Replace `n` with your gimbal output number. **Do not** use motor channels (typically SERVO1–4 on quad).

Bench-test gimbal sweep before flight:

```bash
python hardware/vion/rpi/test_gimbal_sweep.py --profile vivi
```

## GPS and GUIDED

Outdoor autonomy uses **GUIDED** with GPS (not `GUIDED_NOGPS` — no optical flow on Vivi).

- Ensure GPS has lock before velocity commands in flight
- Indoor hover without GPS/flow is not supported on this config

## Battery monitor

Set `BATT_MONITOR` and related params so `SafetyMonitor` can read `SYS_STATUS.battery_remaining`.

## No spray on Vivi

Vivi has no water payload. The `vivi` flight profile sets `spray.method: none`.

## Firmware check

Mission Planner top bar should show ArduPilot modes (Stabilize, Loiter, Guided, etc.). If you see Betaflight-style OSD only, reflash ArduPilot for Kakute H7.
