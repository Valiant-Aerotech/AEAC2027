# Outdoor field day (orbit + mission dry-run)

Two-run field day: **Run 1** validates GUIDED orbit (no CV). **Run 2** exercises
survey / tagtrack companion paths after SITL has already passed.

Fresh Pi: [pi-fresh-install.md](pi-fresh-install.md). Orbit detail: [vivi-orbit-field-test.md](vivi-orbit-field-test.md).

## Before you leave

- [ ] `pip install -e ../valiant-mav` on laptop and Pi
- [ ] `python tools\valiant.py quickstart` OK
- [ ] `python tools\valiant.py survey --dry-run` and `tagtrack --dry-run` OK
- [ ] SITL `sitl pattern` / `sitl orbit --laps 1` OK once
- [ ] `safety.lua` on FC SD card; kill switch polarity bench-tested props-off
- [ ] Boundary poly loaded in Mission Planner (`valiant boundary export`)
- [ ] Laptop WiFi IP known for `--gcs-ip`

## Run 1 — GUIDED orbit

**Goal:** Manual takeoff → flip **GUIDED** → 1 lap → hold / hand back → manual home. No CV.

```bash
# On Pi
bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <laptop-ip> --laps 1
```

Or from GCS laptop against Pi UART: `python tools\valiant.py field orbit --gcs-ip <ip> --laps 1`.

Pilot steps and kill-switch notes: [vivi-orbit-field-test.md](vivi-orbit-field-test.md).

## Run 2 — Survey / tagtrack companion

**Goal:** Confirm competition loopback, HUD labels, and report/CSV paths on the
aircraft link. Prefer `--dry-run` until the live sweep is gated in SITL.

```powershell
python tools\valiant.py survey --dry-run --report artifacts/field_survey.txt
python tools\valiant.py tagtrack --dry-run --log artifacts/field_track.csv
```

Live MAVLink (after SITL gate): drop `--dry-run` and pass `--connection` for the
Pi UART or SITL URL. Soft boundary → hold; never rely on Python for FTS.

## Abort / recovery

| Event | Expected |
|-------|----------|
| Soft boundary | STATUSTEXT + GUIDED hold; pilot recovers |
| Kill switch (RC8) | FC LAND via `safety.lua` |
| Leave GUIDED | Companion stops velocities (pilot override) |
| Uncaught software fault | `hold_after_fault` + crew notify |

Rules map: [docs/conops-2027.md](../conops-2027.md).
