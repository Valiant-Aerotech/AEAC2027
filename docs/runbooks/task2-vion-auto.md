# Runbook - Task 2 Vion Auto Extinguish

## Prerequisites

- Vion armed and in GUIDED mode (operator responsibility)
- Mission Planner telemetry link active
- Phone connected for scrcpy (`ExtinguisherCam` window)
- `config/vion.yaml` COM port set for this laptop

## Run

```powershell
python missions\task2_vion_auto_extinguish.py
python missions\task2_vion_auto_extinguish.py --sim          # no MAVLink commands
python missions\task2_vion_auto_extinguish.py --headless   # no debug window
```

## Abort

Press Ctrl+C - orchestrator sends zero velocity on exit.

## Fallback

If autonomy fails, use `missions/task2_vion_manual_photo.py`.
