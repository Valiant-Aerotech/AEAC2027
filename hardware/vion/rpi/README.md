# Vion Raspberry Pi companion

Onboard flight computer for Task 2 autonomy.

**Bringup:** [docs/runbooks/vion-bringup.md](../../../docs/runbooks/vion-bringup.md)

## Script flow (first time)

```bash
bash hardware/vion/rpi/first_connect.sh          # once
bash hardware/vion/rpi/session_start.sh          # every session
bash hardware/vion/rpi/capture_all_calibration.sh
GCS_IP=<laptop-ip> bash hardware/vion/rpi/run_bringup_tests.sh
bash hardware/vion/rpi/preflight_indoor.sh       # before props on
python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1
```

## Scripts

| Script | Phase | Purpose |
|--------|-------|---------|
| `first_connect.sh` | C | First SSH: setup + checks |
| `setup.sh` | C | venv, deps (called by first_connect) |
| `session_start.sh` | C5 | Quick `--once` sensor check |
| `check_sensors.py` | C5 | RGB, depth, MAVLink (`--once` for pass/fail) |
| `capture_all_calibration.sh` | C6 | 1/2/3 m calibration captures |
| `capture_calibration_set.py` | C6 | Single distance capture |
| `run_bringup_tests.sh` | C7-D | Sim + tethered + optional monitor |
| `preflight_indoor.sh` | E | Props-on checklist |
| `run_mission.py` | E | Autonomous flight (CV orchestrator) |
| `run_field_orbit.py` | E | GUIDED-triggered orbit, then LOITER (no CV) |

## GCS pairing scripts

| Script | Purpose |
|--------|---------|
| `tools/deploy/deploy_to_pi.ps1` | Copy model + calibration to Pi |
| `tools/calibrate/run_calibration_pipeline.ps1` | Pull captures, validate, push yaml |
| `python tools/valiant.py gcs monitor` | Start mission monitor (see [tools/README.md](../../../tools/README.md)) |
