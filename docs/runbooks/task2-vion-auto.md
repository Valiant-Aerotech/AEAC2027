# Runbook - Task 2 Vion Auto Extinguish

## Prerequisites

- Vion armed and in GUIDED mode (operator responsibility)
- Mission Planner telemetry link active
- Phone connected for scrcpy (`ExtinguisherCam` window)
- `config/vion.yaml` COM port set for this laptop
- Emergency RC switch tested (onboard `hardware/vion/lua/safety.lua`)

## Run

```powershell
python missions\task2_vion_auto_extinguish.py
python missions\task2_vion_auto_extinguish.py --sim          # no MAVLink commands
python missions\task2_vion_auto_extinguish.py --headless   # no debug window
python missions\task2_vion_auto_extinguish.py --scrcpy-ip 192.168.1.100:5555
python missions\task2_vion_auto_extinguish.py --max-targets 1   # single-target test
```

CONOPS rules: `config/conops.yaml`. Multi-target loop runs until Ctrl+C or `--max-targets`.

## Abort conditions

| Trigger | Behavior | Config key |
|---------|----------|------------|
| Ctrl+C | Zero velocity, clean shutdown | - |
| Target lost 30 frames | Return to SEARCHING | `cv.max_frames_without_target` |
| Approach / aim timeout | Return to SEARCHING | `auto_nav.approach_timeout_s`, `lock_timeout_s` |
| Side clearance too low | Stop, return to SEARCHING | `auto_nav.side_clearance_m` |
| Battery below 20% | Full mission abort | `safety.min_battery_pct` |
| Geofence breach | Full mission abort | `safety.geofence_abort` |
| Mission timeout (10 min) | Full mission abort | `safety.mission_timeout_s` |

Full safety aborts stop the orchestrator loop, send zero velocity, and optionally command RTL when `safety.rtl_on_abort: true`.

## scrcpy latency tuning

Edit `camera` in `config/vion.yaml`:

- `max_fps` - higher is smoother but more CPU (try 30 or 60)
- `max_size` - lower resolution reduces capture latency (try 960 or 1280)
- `video_bit_rate_mbps` - 4-12 typical; lower can reduce lag on weak USB
- `min_grab_interval_s` - set 0.033 to cap grabs at ~30 Hz if CPU is high

If the scrcpy window is slow to appear, wait until `ExtinguisherCam` is visible before arming.

## Upload

Photos save to `task2_photos/` then copy to `task2_photos/uploaded/`. For real Google Drive:

1. Place service account JSON at `config/gdrive_credentials.json` (gitignored)
2. Set `upload.method: gdrive_service_account` and `upload.folder_id` in `config/defaults.yaml`
3. `pip install google-api-python-client google-auth`

## Fallback

If autonomy fails, use `missions/task2_vion_manual_photo.py` with `--source scrcpy --upload`.
