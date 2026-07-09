# What is left before first drone + Pi hardware test

Read this before connecting to Vion. Bringup: [vion-bringup.md](vion-bringup.md). **Fresh Pi + field day:** [pi-fresh-install.md](pi-fresh-install.md).

## Outdoor field day (Vivi) — software ready

| Item | Status | Command |
|------|--------|---------|
| Run 1 orbit | **Ready** | `pi_field_ready.sh --orbit --gcs-ip <ip> --laps 1` |
| Run 2 outdoor mission | **Ready** | `pi_field_ready.sh --mission --gcs-ip <ip> --max-targets 1` |
| LOITER on COMPLETE | **Ready** | `vivi_outdoor_mission` profile |
| GUIDED standby | **Ready** | `mission.pilot_standby` in profile |
| Retreat before LOITER | **Ready** | `STATE_RETREAT` on hardware |
| Pi bootstrap script | **Ready** | `pi_field_ready.sh --first-time` / `--check` |

Deploy latest code to Pi before field: `.\tools\deploy\deploy_to_pi.ps1 -PiHost user@ip`

## You can test today (software ready)

| Item | Status | Command |
|------|--------|---------|
| GCS env + CONOPS | Ready | `python tools\valiant.py bringup phase1` |
| MAVLink heartbeat (radio) | Ready | `python tools\valiant.py gcs heartbeat` |
| SERVO15 spray bench | Ready | `python tools\valiant.py gcs spray` |
| Pi first SSH setup | Ready | `bash hardware/vion/rpi/pi_field_ready.sh --first-time` |
| Pi sensor check (RGB + MAVLink) | Ready | `bash hardware/vion/rpi/pi_field_ready.sh --check` |
| Sim state machine (no props) | Ready | `run_mission.py --profile indoor --sim` |
| GCS monitor | Ready | `run_mission.py --gcs-ip <laptop-ip> --sim` + `python tools/valiant.py gcs monitor` |

## You must do manually (hardware / ops)

| Item | Why | Action |
|------|-----|--------|
| Deploy `dry.onnx` / `best.onnx` to Pi | Gitignored model | `.\tools\deploy\deploy_to_pi.ps1 -PiHost user@ip` |
| Pi ↔ Kakute UART wiring | Companion MAVLink | [hardware/vivi/WIRING.md](../../hardware/vivi/WIRING.md) |
| Pi serial permissions | `/dev/ttyAMA0` | `sudo usermod -aG dialout $USER`, re-login |
| Enable Pi UART | MAVLink to FC | `enable_uart=1` or raspi-config, reboot |
| Kakute TELEM params | Pi link | `SERIALx_PROTOCOL=2`, `SERIALx_BAUD=57` on Pi port only |
| Manual arm + climb | No auto takeoff | Pilot arms and climbs before GUIDED / orbit |
| RC override + emergency switch | Safety | Test in Mission Planner before props on |
| H-Flow (indoor only) | Not required outdoor | Skip for parking-lot GPS day |

## Not implemented yet (expect degraded behavior)

| Item | Impact today | Workaround |
|------|--------------|------------|
| **ArduCam ToF driver** | FOV range estimate outdoors | Accept approximate approach; tune after flight |
| **Real depth calibration** | 10% gate strict indoors | Outdoor GPS day OK without ToF |
| **Auto takeoff / land** | Velocity only when armed + airborne | Manual climb; LOITER handoff at end |
| **Google Drive upload on Pi** | Photos save locally | `scp` from Pi after flight |
| **Shot ONNX** | Shot confirm uses HSV blue only | Wet target within 8 s of FIRING |

## Code fixes applied (field-ready)

- `pi_field_ready.sh` — unified Pi setup, check, orbit, mission
- Hardware LOITER on mission COMPLETE + retreat before LOITER
- `vivi_outdoor_mission` profile (spray, GUIDED standby, outdoor tuning)
- `load_config("vivi")` inherits `vion.yaml` flight profiles
- Deploy script copies `dry.onnx` and/or `best.onnx`

## Recommended test order

1. **GCS + drone (props off):** MP connect, params, spray test, `gcs verify-safety`
2. **Pi SSH:** `pi_field_ready.sh --first-time`, laptop `deploy_to_pi.ps1`
3. **Pi + FC (props off):** wire per WIRING.md → `pi_field_ready.sh --check`
4. **Field Run 1:** orbit `--laps 1` in parking lot (GPS)
5. **Field Run 2 (optional):** mission `--max-targets 1` with pole target

## When you are "ready to fly" outdoors (Run 1 minimum)

- [ ] `pi_field_ready.sh --check` passes (RGB + MAVLink + safety.lua)
- [ ] `python tools\valiant.py gcs verify-safety` passes
- [ ] Messages: `safety: kill monitor loaded (RC8)`
- [ ] Pi UART wired to **separate** FC port from GCS radio
- [ ] Mode switch maps to **GUIDED**
- [ ] 3D GPS fix outdoors
- [ ] Kill switch tested (props off) → FC LAND
- [ ] Laptop `gcs monitor` + Pi `--gcs-ip` set to laptop WiFi IP

Run 2 additionally: `dry.onnx` on Pi, purple target, wet-test plan.
