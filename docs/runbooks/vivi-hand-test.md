# Hand-carry bench test — Vivi + Kakute H7 + pitch gimbal

Props **off**. Pi runs full perception; GCS monitors only. Drone velocity and spray are disabled in `--hand-test`; **gimbal servo still moves** when a target is in view.

## Prerequisites

- Kakute H7 running **ArduPilot** ([`hardware/vivi/mission-planner/001-kakute-h7.md`](../../hardware/vivi/mission-planner/001-kakute-h7.md))
- Pi UART on dedicated FC port; GCS telemetry on a **separate** port
- Set `flight_profiles.vivi.gimbal.channel` in [`config/vion.yaml`](../../config/vion.yaml) to your AUX output
- Tune `pwm_min` / `pwm_max` / `pwm_neutral` on bench with:

```bash
python hardware/vion/rpi/test_gimbal_sweep.py --profile vivi
```

## GCS

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
python tools\valiant.py gcs monitor
```

Mission Planner @ 57600 (telemetry radio) — heartbeat OK.

## Pi — link check

```bash
cd ~/AEAC2027 && source .venv/bin/activate
export PYTHONPATH=src
bash hardware/vion/rpi/session_start.sh
```

Pass: RGB frame + MAVLink heartbeat on Pi UART.

## Pi — hand-carry mission

```bash
python hardware/vion/rpi/run_mission.py --profile vivi --hand-test --headless --max-targets 1 --gcs-ip <laptop-ip>
```

## Procedure

1. Power FC + Pi. Props off.
2. Start GCS monitor, then Pi mission.
3. Optionally preset gimbal pitch in Mission Planner servo tab, or let autonomy drive pitch when target is visible.
4. Hold the airframe and move toward/away from a purple target.
5. Move target up/down in the frame — gimbal should pitch to track (PWM logged on Pi console in hand-test).

## Pass criteria

| Check | Expected |
|-------|----------|
| Monitor `target_seen` | `Y` when aimed at target |
| State | `SEARCHING` → `APPROACHING` → `AIMING` |
| Distance | Band or value updates as you move |
| Monitor `hand` | `Y` (no drone velocity) |
| MP HUD | `T2:` statustext from Pi |
| Gimbal | Pitch moves when target off-centre vertically (optional first pass: fixed manual pitch OK) |

## Next steps

1. Tethered test **without** `--hand-test` (props off, hold frame) — drone horizontal velocity only; gimbal handles pitch.
2. Outdoor flight with GPS lock in GUIDED.

## Spray

Vivi profile sets `spray.method: none` — no water servo commands.
