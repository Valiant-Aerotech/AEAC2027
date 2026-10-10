# Vion / Vivi first-time bringup (drone + Pi)

**Fresh Raspberry Pi OS:** [pi-fresh-install.md](pi-fresh-install.md).

Two independent MAVLink links. Do not put GCS radio and Pi on the same Pixhawk serial port.

| Link | Path | Role |
|------|------|------|
| GCS telemetry radio | COM port → Pixhawk | Mission Planner, params, advisory readback |
| Pi companion | `/dev/ttyAMA0` @ 57600 → TELEM | Survey / tagtrack / field orbit |
| GCS WiFi monitor | Pi UDP → laptop | Read-only `python tools\valiant.py gcs monitor` |

## Script map

| Phase | GCS (PowerShell) | Pi (bash) |
|-------|------------------|-----------|
| B - GCS connect | `.\tools\gcs\bringup_gcs.ps1` | — |
| B - MAVLink | `python tools\valiant.py gcs heartbeat` | — |
| B - FC params (advisory) | `python tools\valiant.py gcs params` | — |
| C - First SSH | `.\tools\deploy\deploy_to_pi.ps1 -PiHost user@ip` | `bash hardware/vion/rpi/first_connect.sh` |
| C - Sensors | — | `bash hardware/vion/rpi/pi_field_ready.sh --check` |
| C - Calibration | `.\tools\calibrate\run_calibration_pipeline.ps1` | `bash hardware/vion/rpi/capture_all_calibration.sh` |
| D - Monitor | `python tools\valiant.py gcs monitor` | — |
| E - Field orbit | `python tools\valiant.py gcs monitor` | `bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <ip> --laps 1` |
| E - Survey / tagtrack | dry-run on laptop first | `python tools/valiant.py survey` / `tagtrack` when wired on Pi |

Props off until tethered checks pass. Safety: load `hardware/vion/lua/safety.lua`, confirm with `gcs verify-safety` if available.

## GCS laptop

1. Plug telemetry radio; note COM port.
2. Mission Planner → Connect @ **57600**.
3. Confirm heartbeat, battery, GPS.
4. Set fence / `LAND_SPEED` per [docs/conops-2027.md](../conops-2027.md) (FC owns FTS).
5. Enable Lua scripting; load kill-switch `safety.lua`.
6. `python tools\valiant.py gcs heartbeat` and `gcs params`.

```powershell
cd <repo>
.\tools\gcs\bringup_gcs.ps1
```

## Raspberry Pi

```bash
ssh <user>@<pi-ip>
cd ~/AEAC2027   # or clone fresh
bash hardware/vion/rpi/first_connect.sh
bash hardware/vion/rpi/pi_field_ready.sh --check
```

Install sibling `valiant-mav` on the Pi the same way as the laptop (`pip install -e ../valiant-mav`).

### Field orbit (no CV)

```bash
bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <laptop-ip> --laps 1
```

See [vivi-orbit-field-test.md](vivi-orbit-field-test.md).

## Physical checks

- [ ] Optical flow / GPS rigid and facing down as designed
- [ ] Pi UART on a dedicated TELEM port (not the GCS radio port)
- [ ] Camera + ToF on Pi (ToF is **not** used for Task 1 ground range — GPS + projection)
- [ ] GCS laptop on same WiFi as Pi for UDP monitor
- [ ] Props off until tethered tests pass

Companion never terminates the aircraft. Soft boundary → hold + STATUSTEXT only.
