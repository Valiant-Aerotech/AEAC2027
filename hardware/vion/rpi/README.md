# Vion Raspberry Pi companion

Onboard flight computer for Task 2 autonomy: CV, metric recon (ArduCam ToF), PD nav, MAVLink to Pixhawk.

## Wiring

| Link | Connection |
|------|------------|
| Pi UART to Pixhawk TELEM | `/dev/ttyAMA0` at 57600 (enable UART in boot config) |
| Holybro H-Flow | DroneCAN on Pixhawk CAN bus (with HERE4); downward facing |
| AI camera + ArduCam ToF | Pi CSI/USB per mount |

GCS laptop connects over WiFi UDP for monitor only (`tools/mission_monitor.py`).

## Scripts

| Script | Purpose |
|--------|---------|
| `setup.sh` | Pi venv, package install, calibration template |
| `check_sensors.py` | RGB preview, depth stats, MAVLink heartbeat |
| `capture_calibration_set.py` | Save RGB+depth at tape distances |
| `run_mission.py` | Primary autonomous entry |

## First-time flow

```bash
cd AEAC2027
sudo bash hardware/vion/rpi/setup.sh
source .venv/bin/activate
python hardware/vion/rpi/check_sensors.py
python hardware/vion/rpi/capture_calibration_set.py --distance 1.0
python hardware/vion/rpi/capture_calibration_set.py --distance 2.0
python hardware/vion/rpi/capture_calibration_set.py --distance 3.0
# copy logs/calibration to GCS, run tools/validate_calibration.py
python hardware/vion/rpi/run_mission.py --profile indoor --sim
python hardware/vion/rpi/run_mission.py --profile indoor
```

## Indoor flight

- `flight.profile: indoor` sets `GUIDED_NOGPS`, disables GPS requirement
- H-Flow provides optical flow + downward lidar for EKF (not target range)
- ArduCam ToF on Pi provides `depth_at_target` for approach and fire distance

See `docs/runbooks/indoor-flight.md` and `hardware/vion/mission-planner/001-parameters.md`.
