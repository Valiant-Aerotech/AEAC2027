# Vion Raspberry Pi companion

Onboard flight computer for Task 2 autonomy.

**Start here:** [docs/runbooks/pi-fresh-install.md](../../../docs/runbooks/pi-fresh-install.md) (fresh Pi OS → field flight)

**Bringup detail:** [docs/runbooks/vion-bringup.md](../../../docs/runbooks/vion-bringup.md)

## One script (recommended)

```bash
bash hardware/vion/rpi/pi_field_ready.sh --first-time          # once after fresh OS
bash hardware/vion/rpi/pi_field_ready.sh --check             # every session
bash hardware/vion/rpi/pi_field_ready.sh --orbit --gcs-ip <IP> --laps 1
bash hardware/vion/rpi/pi_field_ready.sh --mission --gcs-ip <IP> --max-targets 1
```

`first_connect.sh` and `session_start.sh` delegate to `pi_field_ready.sh`.

## Script map

| Script | Purpose |
|--------|---------|
| **`pi_field_ready.sh`** | **Primary entry:** setup, check, orbit, mission |
| `first_connect.sh` | Alias for `--first-time` |
| `session_start.sh` | Alias for `--check` |
| `setup.sh` | venv + pip (called by `--first-time`) |
| `check_sensors.py` | RGB, depth, MAVLink, safety.lua |
| `run_field_orbit.py` | GUIDED orbit → LOITER (Run 1) |
| `run_mission.py` | CV mission orchestrator (Run 2) |
| `preflight_indoor.sh` | Props-on indoor checklist |
| `run_bringup_tests.sh` | Sim + tethered tests |
| `capture_all_calibration.sh` | 1/2/3 m calibration captures |

Before props-on flight: `python tools/valiant.py gcs verify-safety` (included in `--check` when MAVLink up).

## GCS pairing (laptop)

| Script | Purpose |
|--------|---------|
| `tools/deploy/deploy_to_pi.ps1` | Copy repo + model to Pi |
| `python tools/valiant.py gcs monitor` | UDP status monitor |
| `python tools/valiant.py gcs verify-safety` | safety.lua + SCR_ENABLE |
