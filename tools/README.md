# Valiant AEAC2027 tools

Use **`python tools/valiant.py --help`** for the unified CLI. Platform scripts (WSL, ssh/scp) stay as thin `.ps1` wrappers.

## Daily workflows

| Task | Command |
|------|---------|
| SITL: start simulator | `.\tools\launch_sitl.ps1` |
| SITL: run mission | `python tools/valiant.py sitl mission` or `.\tools\run_sitl_mission.ps1` |
| SITL: run tests | `python tools/valiant.py sitl test` |
| GCS telemetry HUD | `python tools/valiant.py gcs monitor` |
| CV bench (webcam) | `python tools/valiant.py bench cv` |
| Metric + 3D recon bench | `python tools/valiant.py bench metric` |
| Validate CONOPS config | `python tools/valiant.py conops check` |
| Check Python env | `python tools/valiant.py env check` |
| Calibration pipeline | `.\tools\run_calibration_pipeline.ps1` |
| Deploy to Pi | `.\tools\deploy_to_pi.ps1` |
| First GCS connect | `.\tools\bringup_gcs.ps1` |

## CLI groups

- **`env`** / **`conops`**: setup validation
- **`gcs`**: heartbeat, spray test, monitor, MAVLink listen
- **`sitl`**: mission, tests, map download
- **`bench`**: cv, metric, safety
- **`calibrate`**: tune, validate, replay Pi captures

## Platform scripts (not in CLI)

| Script | Purpose |
|--------|---------|
| `setup.ps1` | Create Windows venv |
| `launch_sitl.ps1` / `sitl/launch_sitl.sh` | WSL ArduPilot SITL |
| `deploy_to_pi.ps1` | scp repo to Pi |
| `run_calibration_pipeline.ps1` | pull, validate, push calibration |
| `bringup_gcs.ps1` | first-connect checklist |
| `create_github_issues.ps1` | backlog admin (one-off) |

Removed passthrough wrappers: use `valiant.py gcs monitor` and `valiant.py sitl map download` instead of `run_monitor.ps1` and `download_sitl_map.ps1`.
