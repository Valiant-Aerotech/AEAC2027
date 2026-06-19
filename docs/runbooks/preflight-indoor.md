# Pre-flight indoor (props on)

Run after bringup Phases B-D pass. See [vion-bringup.md](vion-bringup.md).

## Automated checklist (Pi)

```bash
cd ~/AEAC2027
bash hardware/vion/rpi/preflight_indoor.sh
```

## Manual checks (GCS + spotter)

- [ ] Mission Planner heartbeat via telemetry radio
- [ ] H-Flow `opt_qua` OK on hover over venue-like floor
- [ ] Emergency RC switch tested
- [ ] Water tank filled; SERVO15 verified
- [ ] Spotter assigned; RC pilot ready to override
- [ ] GCS `python tools\valiant.py gcs monitor` (optional)

## Run flight

```bash
# Pi
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1 \
  --gcs-connection udpout:<LAPTOP_IP>:14550
```

```powershell
# GCS
python tools\valiant.py gcs monitor
```

## Pass criteria (Phase E)

- One full cycle: detect, approach, 2 m gate, aim, spray, verify shot, photo
- RC override works if pilot takes GUIDED/GUIDED_NOGPS away from Pi
- Ctrl+C on Pi zeros velocity
