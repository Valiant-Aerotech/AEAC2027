# Vion First-Time Bringup (Drone + Pi)

Two independent MAVLink links. Do not put GCS radio and Pi on the same Pixhawk serial port.

| Link | Path | Role |
|------|------|------|
| GCS telemetry radio | COM port -> Pixhawk | Mission Planner, params, spray test, H-Flow bench |
| Pi companion | `/dev/ttyAMA0` @ 57600 -> TELEM | Autonomous mission control |
| GCS WiFi monitor | Pi UDP -> laptop | Read-only `mission_monitor.py` |

Script map by phase:

| Phase | GCS (PowerShell) | Pi (bash) |
|-------|------------------|-----------|
| B - GCS connect | `.\tools\bringup_gcs.ps1` | - |
| B - MAVLink | `python tools\check_mavlink_gcs.py` | - |
| B - Spray test | `python tools\test_spray_gcs.py` | - |
| B - FC params | `.\tools\print_fc_params.ps1` | - |
| C - First SSH | `.\tools\deploy_to_pi.ps1 -PiHost user@ip` | `bash hardware/vion/rpi/first_connect.sh` |
| C - Sensors | - | `bash hardware/vion/rpi/session_start.sh` |
| C - Calibration | `.\tools\run_calibration_pipeline.ps1 -PiHost user@ip` | `bash hardware/vion/rpi/capture_all_calibration.sh` |
| C/D - Sim/tether/monitor | `.\tools\run_monitor.ps1` | `GCS_IP=<ip> bash hardware/vion/rpi/run_bringup_tests.sh` |
| E - Preflight | - | `bash hardware/vion/rpi/preflight_indoor.sh` |
| E - Flight | `.\tools\run_monitor.ps1` | `python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1` |

**Before hardware day:** [whats-left-before-hardware.md](whats-left-before-hardware.md)

Props off until tethered tests pass.

---

## Run first: GCS laptop (connect to drone)

### 1. Mission Planner (manual)

1. Plug telemetry radio USB; note COM port (Device Manager)
2. Mission Planner -> Connect @ **57600**
3. Confirm heartbeat, battery, HERE4/GPS status
4. `.\tools\print_fc_params.ps1` then set params in MP (see [002-pi-telem-params.md](../../hardware/vion/mission-planner/002-pi-telem-params.md))
5. Confirm DroneCAN sees H-Flow
6. `python tools\test_spray_gcs.py` (SERVO15, props off)
7. Test emergency RC switch (Lua `safety.lua`)

### 2. GCS repo scripts

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\tools\bringup_gcs.ps1
```

---

## Run first: Raspberry Pi (first SSH session)

```bash
ssh <user>@<pi-ip>
cd ~
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
bash hardware/vion/rpi/first_connect.sh
```

From GCS laptop:

```powershell
.\tools\deploy_to_pi.ps1 -PiHost <user>@<pi-ip>
```

### UART (if first_connect warns)

```bash
sudo raspi-config
# Serial Port -> login shell No, hardware Yes
sudo reboot
```

### Every session

```bash
source .venv/bin/activate
bash hardware/vion/rpi/session_start.sh
```

### Calibration

```bash
bash hardware/vion/rpi/capture_all_calibration.sh
```

```powershell
.\tools\run_calibration_pipeline.ps1 -PiHost <user>@<pi-ip>
```

### Sim, tethered, monitor

```bash
GCS_IP=<laptop-ip> bash hardware/vion/rpi/run_bringup_tests.sh
```

```powershell
.\tools\run_monitor.ps1
```

### Props-on preflight

```bash
bash hardware/vion/rpi/preflight_indoor.sh
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1
```

---

## Phase A - Physical checks

- [ ] H-Flow rigid, facing down, DroneCAN with HERE4
- [ ] Pi UART on dedicated TELEM port (not GCS radio port)
- [ ] AI camera + ArduCam ToF on Pi
- [ ] GCS laptop on same WiFi as Pi
- [ ] Props off until tethered tests pass

**Note:** ArduCam ToF requires SDK install on Pi (`install_arducam_tof.sh`). Until then depth shows `n/a` and FOV fallback applies.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Pi no heartbeat | Enable UART; check `/dev/ttyAMA0`; `SERIALx_PROTOCOL=2` on FC |
| MP + Pi conflict | Use different FC serial ports |
| `opt_qua` low | H-Flow mount, fly 0.5-3 m AGL, venue-like floor |
| `depth: n/a` | ArduCam driver pending; FOV fallback active |
| Monitor LOST | Firewall; `--gcs-connection udpout:<LAPTOP_IP>:14550` |
| No YOLO hits | `models/best.onnx` on Pi; lighting; purple target in frame |
