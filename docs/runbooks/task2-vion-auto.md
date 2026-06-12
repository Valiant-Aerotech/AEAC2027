# Runbook - Task 2 Vion Auto Extinguish

## Primary path (onboard RPi)

Competition autonomous runs on the Pi companion, not the GCS laptop.

```bash
# on Pi
source .venv/bin/activate
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1
```

GCS monitor (optional, same WiFi):

```powershell
python tools\mission_monitor.py
```

First-time setup: [vion-bringup.md](vion-bringup.md)

## GCS dev / legacy path (scrcpy)

For bench without Pi:

```powershell
.\tools\webcam_bench.ps1
python missions\task2_vion_auto_extinguish.py --sim --source webcam --camera 0 --max-targets 1
```

## Prerequisites (onboard flight)

- Pi `check_sensors.py` passes (RGB + MAVLink heartbeat)
- `config/vion_calibration.yaml` on Pi (10% gate via `tools\validate_calibration.py`)
- Vion in GUIDED_NOGPS for indoor (`--profile indoor`)
- Holybro H-Flow configured; `opt_qua` OK on venue-like floor
- Emergency RC switch tested (`hardware/vion/lua/safety.lua`)
- Spotter + RC override ready

## Run (GCS legacy)

```powershell
python missions\task2_vion_auto_extinguish.py
python missions\task2_vion_auto_extinguish.py --sim --source webcam --camera 0
python missions\task2_vion_auto_extinguish.py --max-targets 1
```

## Abort conditions

| Trigger | Behavior | Config key |
|---------|----------|------------|
| Ctrl+C | Zero velocity, clean shutdown | - |
| RC mode change | Nav stop, return to SEARCHING | flight.mode |
| Target lost 30 frames | Return to SEARCHING | `cv.max_frames_without_target` |
| Approach / aim timeout | Return to SEARCHING | `auto_nav.approach_timeout_s`, `lock_timeout_s` |
| Side clearance too low | Stop, return to SEARCHING | `auto_nav.side_clearance_m` |
| Battery below 20% | Full mission abort | `safety.min_battery_pct` |
| Geofence breach | Full mission abort | `safety.geofence_abort` |
| GCS WiFi lost | Mission continues on Pi | gcs_monitor (read-only) |

## Fallback

```powershell
python missions\task2_vion_manual_photo.py --source scrcpy --upload
```
