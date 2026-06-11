# Runbook - Competition Day Checklist

Use this on Phase 2 flight line for Vion Task 2 and Vivi Task 1.

## Before leaving for site

- [ ] `python tools\verify_env.py` passes on competition laptop
- [ ] `python tools\conops_check.py` passes
- [ ] `config\vion.yaml` COM port correct
- [ ] `config\defaults.yaml` team name and upload settings correct
- [ ] Phone charged, scrcpy + adb on PATH
- [ ] Emergency RC switch tested (`hardware/vion/lua/safety.lua`)
- [ ] Water tank filled, servo spray tested on bench

## Task 2 - Vion auto (flight window)

### Pre-flight

- [ ] Vion in GUIDED mode, geofence loaded in Mission Planner
- [ ] Telemetry heartbeat confirmed
- [ ] scrcpy `ExtinguisherCam` window visible
- [ ] Operator briefed: Ctrl+C abort, manual fallback ready

### Run

```powershell
python missions\task2_vion_auto_extinguish.py
```

For a single-target test before full window:

```powershell
python missions\task2_vion_auto_extinguish.py --max-targets 1
```

### During flight

- [ ] Declare each extinguished target to judges per CONOPS
- [ ] Confirm HUD / console shows upload for each target number
- [ ] Photos appear in `task2_photos/` as `Task_2_{team}_target_{n}.jpg`
- [ ] Refill water between targets as needed (unlimited refills allowed)

### If autonomy fails

```powershell
python missions\task2_vion_manual_photo.py --source scrcpy --upload
```

## Task 1 - Vivi survey (flight window)

```powershell
python missions\task1_vivi_survey.py --team "ValiantAerotech"
```

- [ ] Upload `Task_1_{team}_targets.txt` to team Google Drive before window ends

## Post-flight

- [ ] Verify all Task 2 photos in Google Drive with correct numbering order
- [ ] Note any safety aborts or shot confirmation timeouts for debrief
- [ ] Battery data and log any geofence warnings

## CONOPS quick reference

- Autonomous extinguishing: approach >2 m, aim, fire, photo, upload - all autonomous, no partial points
- Target count unknown - keep looping until window ends or operator stops
- Only water may touch targets

See [docs/conops.md](../conops.md) for full traceability.
