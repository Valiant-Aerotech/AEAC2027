# Runbook - Competition Day Checklist

Use this on Phase 2 flight line for Vion Task 2 and Vivi Task 1.

Bringup reference: [vion-bringup.md](vion-bringup.md)

## Before leaving for site

- [ ] `python tools\valiant.py env check` passes on competition laptop
- [ ] `python tools\valiant.py conops check` passes
- [ ] `config\rpas.yaml` COM port correct (GCS radio)
- [ ] `config\defaults.yaml` team name and upload settings correct
- [ ] Pi has dry YOLO weights (`models/dry.onnx` or `models/best.onnx`) and `config/rpas_calibration.yaml` (or legacy `vion_calibration.yaml`)
- [ ] `python tools\valiant.py gcs verify-safety` passes (SCR_ENABLE + `scripts/safety.lua`)
- [ ] Mission Planner Messages shows `safety: kill monitor loaded (RC8)` after FC reboot
- [ ] Emergency RC switch tested (flip → LAND; see [`hardware/vion/lua/safety.lua`](../../hardware/vion/lua/safety.lua))
- [ ] Water tank filled, SERVO15 spray tested in Mission Planner
- [ ] H-Flow `opt_qua` OK on venue-like flooring (indoor)

## Task 2 - Vion auto (flight window)

### Pre-flight

- [ ] Pi: `check_sensors.py --once` OK (RGB + MAVLink + safety.lua when FC connected)
- [ ] GCS: `python tools\valiant.py gcs verify-safety` OK
- [ ] GCS: Mission Planner heartbeat via telemetry radio
- [ ] GCS: `python tools\valiant.py gcs monitor` running (optional)
- [ ] Operator briefed: RC override, emergency switch

### Run (primary - onboard Pi)

```bash
# SSH to Pi
source .venv/bin/activate
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1
```

With GCS monitor on laptop (replace LAPTOP_IP):

```bash
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1 \
  --gcs-connection udpout:<LAPTOP_IP>:14550
```

### During flight

- [ ] Declare each extinguished target to judges per CONOPS
- [ ] GCS monitor shows GOOD link (optional)
- [ ] Photos appear in `task2_photos/` on Pi as `Task_2_{team}_target_{n}.jpg`
- [ ] Refill water between targets as needed

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
