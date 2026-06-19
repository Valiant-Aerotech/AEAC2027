# What is left before first drone + Pi hardware test

Read this before connecting to Vion. Bringup steps: [vion-bringup.md](vion-bringup.md).

## You can test today (software ready)

| Item | Status | Command |
|------|--------|---------|
| GCS env + CONOPS | Ready | `.\tools\bringup_gcs.ps1` |
| MAVLink heartbeat (radio) | Ready | `python tools\valiant.py gcs heartbeat` |
| SERVO15 spray bench | Ready | `python tools\valiant.py gcs spray` |
| Pi first SSH setup | Ready | `bash hardware/vion/rpi/first_connect.sh` |
| Pi sensor check (RGB + MAVLink) | Ready | `bash hardware/vion/rpi/session_start.sh` |
| Sim state machine (no props) | Ready | `run_mission.py --profile indoor --sim` |
| GCS monitor | Ready | `run_mission.py --gcs-ip <laptop-ip> --sim` + `python tools/valiant.py gcs monitor` |

## You must do manually (hardware / ops)

| Item | Why | Action |
|------|-----|--------|
| Deploy `best.onnx` to Pi | Gitignored model | `.\tools\deploy_to_pi.ps1 -PiHost user@ip` |
| Install picamera2 on Pi | Not in pip venv | `sudo apt install python3-picamera2` |
| Pi serial permissions | `/dev/ttyAMA0` | `sudo usermod -aG dialout $USER`, re-login |
| Enable Pi UART | MAVLink to FC | `enable_uart=1` or raspi-config, reboot |
| Pixhawk TELEM params | Pi link | `SERIALx_PROTOCOL=2`, `SERIALx_BAUD=57` on Pi port only |
| H-Flow params + bench hover | Indoor stability | `FLOW_TYPE=6`, `RNGFND1_TYPE=24`; watch `opt_qua` |
| Manual arm + hover | No auto takeoff in code | Pilot arms and hovers before mission nav runs |
| RC override + emergency switch | Safety | Test in Mission Planner before props on |

## Not implemented yet (expect degraded behavior)

| Item | Impact today | Workaround |
|------|--------------|------------|
| **ArduCam ToF driver** | Code wired; needs SDK on Pi | `bash hardware/vion/rpi/install_arducam_tof.sh` then reboot |
| **Real depth calibration** | 10% gate cannot pass without ToF frames | Use `--sim` for pipeline test; calibrate after ArduCam wired |
| **Auto takeoff / land** | Mission sends velocity only when armed + airborne | Manual hover during APPROACHING/AIMING |
| **Google Drive upload on Pi** | Photos save locally | Copy from Pi after flight |
| **Shot ONNX** | Shot confirm uses HSV blue only | Wet target should read blue in frame |

## Code fixes applied for bringup

- Central `apply_vion_profile()` in `src/valiant/autonomy/flight/profile.py`
- Pre-flight warnings in `src/valiant/autonomy/flight/preflight.py`
- CONOPS 2 m gate no longer bypasses when distance unknown (`planner.can_fire`)
- Calibration index paths fixed (`capture_calibration_set.py`, `depth_source.py`)
- `--gcs-ip` on `run_mission.py` for monitor link
- `SKIP_MAVLINK=1` for camera-only Pi check before FC powered
- Disarmed + depth-fallback warnings in orchestrator loop

## Recommended test order

1. **GCS + drone (props off):** MP connect, params, spray test, `bringup_gcs.ps1`
2. **Pi SSH (FC optional):** `first_connect.sh`, `SKIP_MAVLINK=1 session_start.sh` for camera only
3. **Pi + FC (props off):** `session_start.sh` with MAVLink heartbeat
4. **Sim:** `run_mission.py --profile indoor --sim --gcs-ip <ip>`
5. **Tethered (props off, hold frame):** `run_bringup_tests.sh`
6. **Props on:** `preflight_indoor.sh` then `run_mission.py --gcs-ip <ip>`

## When you are "ready to fly" autonomously

All of:

- [ ] `check_sensors.py --once` passes (RGB + MAVLink)
- [ ] `best.onnx` on Pi, purple target detected in sim
- [ ] H-Flow `opt_qua` OK on venue floor (manual hover)
- [ ] SERVO15 + RC emergency tested
- [ ] ArduCam wired OR you accept FOV-only ranging for this session
- [ ] Pilot can arm, hover, and override RC
- [ ] GCS monitor shows `dist_m` and `depth_ok` during sim/tethered

Full extinguish accuracy (2 m gate, 0.8 m fire) requires ArduCam ToF + calibration passing 10% gate.
