# Valiant AEAC2027 tools

**Entry point:** `python tools/valiant.py --help`

Platform scripts (PowerShell / WSL) stay beside the CLI. Python bench/calibration logic lives in `tools/*.py` and is invoked only through `valiant.py` subcommands (do not run those scripts directly).

## Daily workflows

| Task | Command |
|------|---------|
| First-time GCS setup | `.\tools\setup.ps1` |
| First drone connect | `.\tools\bringup_gcs.ps1` |
| SITL: start simulator | `.\tools\launch_sitl.ps1` |
| SITL: run mission | `python tools/valiant.py sitl mission` or `.\tools\run_sitl_mission.ps1` |
| SITL: run tests | `python tools/valiant.py sitl test` |
| GCS telemetry HUD | `python tools/valiant.py gcs monitor` |
| CV bench | `python tools/valiant.py bench cv --camera 0` |
| CV regression on video | `python tools/valiant.py bench cv --regression --video clip.mp4` |
| Metric + 3D recon | `python tools/valiant.py bench metric --camera 0` |
| Webcam smoke (automated) | `.\tools\webcam_bench.ps1` |
| Validate CONOPS | `python tools/valiant.py conops check` |
| Calibration pipeline | `.\tools\run_calibration_pipeline.ps1` |
| Deploy to Pi | `.\tools\deploy_to_pi.ps1` |

## `valiant.py` subcommands

| Group | Commands |
|-------|----------|
| `env` | `check` |
| `conops` | `check` |
| `gcs` | `heartbeat`, `spray`, `monitor`, `listen` |
| `sitl` | `mission`, `test`, `map download` |
| `bench` | `cv`, `metric`, `safety` |
| `calibrate` | `tune`, `validate`, `replay` |

## Files kept in `tools/`

| File | Role |
|------|------|
| `valiant.py` | Unified CLI |
| `setup.ps1` | Windows venv + pip install |
| `bringup_gcs.ps1` | First-connect checklist |
| `launch_sitl.ps1` | WSL ArduPilot launcher |
| `run_sitl_mission.ps1` | SITL mission launcher (profile flags) |
| `run_sitl_tests.ps1` | SITL pytest wrapper |
| `webcam_bench.ps1` | Automated bench smoke |
| `deploy_to_pi.ps1` | scp repo to Pi |
| `run_calibration_pipeline.ps1` | pull / validate / push calibration |
| `copy_calibration_from_pi.ps1` / `copy_calibration_to_pi.ps1` | scp helpers |
| `create_github_issues.ps1` | One-off backlog admin |
| `print_fc_params.ps1` | FC parameter cheat sheet |
| `sitl/launch_sitl.sh` | WSL `sim_vehicle.py` wrapper |
| `sitl/requirements-wsl.txt` | WSL pip deps |

## Implementation modules (via `valiant.py` only)

`verify_env.py`, `conops_check.py`, `check_mavlink_gcs.py`, `test_spray_gcs.py`, `mission_monitor.py`, `mavproxy_listen.py`, `download_sitl_map.py`, `cv_bench_test.py`, `metric_bench_test.py`, `safety_bench_test.py`, `calibrate_depth_rgb.py`, `validate_calibration.py`, `replay_rpi_recording.py`

## Removed (consolidated)

| Removed | Use instead |
|---------|-------------|
| `run_monitor.ps1` | `valiant gcs monitor` |
| `download_sitl_map.ps1` | `valiant sitl map download` |
| `setup_gcs.ps1` | `setup.ps1` + `bringup_gcs.ps1` |
| `yolo_webcam_test.py` | `valiant bench cv` |
| `cv_regression_test.py` | `valiant bench cv --regression --video …` |
