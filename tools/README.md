# Valiant AEAC2027 tools

**New here?** Read [START_HERE.md](../START_HERE.md) first - not this file.

## One command to remember

```powershell
python tools\valiant.py guide
```

No arguments also prints the guide. First laptop setup: `.\start.ps1` from repo root.

---

## Root folder (run these directly)

| Script | When |
|--------|------|
| `valiant.py` | All bench, SITL, GCS, bringup via subcommands |
| `setup.ps1` | First-time venv (`valiant setup` or `start.ps1`) |
| `setup_wsl.ps1` | One-time WSL + ArduPilot |
| `launch_sitl.ps1` | Terminal 1 before SITL mission |
| `run_sitl_mission.ps1` | Default SITL mission (`valiant sitl mission`) |
| `run_sitl_mission_file.ps1` | YAML mission (`valiant sitl run …`) |
| `run_sitl_pattern.ps1` | GUIDED box pattern (`valiant sitl pattern`) |

Everything else lives in subfolders and is invoked via `valiant.py` or the scripts above.

---

## Subfolders

| Folder | Contents |
|--------|----------|
| `lib/` | Shared PS1 helpers (`diagnostics.ps1`, `wsl_distro.ps1`, `guide_text.py`) |
| `sitl/` | WSL bash, SITL tests, map download, YAML mission runner Python |
| `bench/` | `verify_env`, `diagnose`, `conops_check`, CV/metric/safety benches |
| `gcs/` | MAVLink monitor, heartbeat, spray test, `bringup_gcs.ps1` |
| `bringup/` | `phase1_bringup.ps1`, `print_fc_params.ps1` |
| `calibrate/` | Depth/RGB calibration scripts and Pi sync PS1 |
| `deploy/` | `deploy_to_pi.ps1`, upload smoke test |
| `dev/` | `verify_ps1.ps1`, `create_github_issues.ps1` |

---

## Pick your path

| You are… | Run |
|----------|-----|
| **Brand new laptop** | `.\start.ps1` |
| **Check install (no drone)** | `python tools\valiant.py quickstart` |
| **Something failed?** | `python tools\valiant.py diagnose` |
| **Webcam / CV test** | `python tools\valiant.py bench cv --camera 0` |
| **Virtual full mission** | `setup_wsl.ps1` -> `launch_sitl.ps1` -> `valiant sitl mission` |
| **SITL motion check (no CV)** | `launch_sitl.ps1` -> `valiant sitl pattern` |
| **Custom SITL experiment** | Edit `config\sitl_missions\example_wall.yaml`, then `valiant sitl run config\sitl_missions\example_wall.yaml` |
| **Mission Planner T2: test** | SITL running -> `valiant gcs verify-statustext` |
| **First drone connect (GCS)** | `python tools\valiant.py bringup phase1` |
| **Telemetry HUD** | `python tools\valiant.py gcs monitor` |
| **Deploy to Pi** | `.\tools\deploy\deploy_to_pi.ps1 -PiHost user@ip` |

---

## CLI reference

| Group | Commands | Purpose |
|-------|----------|---------|
| *(top)* | `guide`, `quickstart`, `setup`, `diagnose` | Scenario menu, health checks, venv install |
| `env` | `check` | Python packages |
| `conops` | `check` | Competition config |
| `bench` | `cv`, `metric`, `safety`, `smoke` | Laptop tests (no drone) |
| `sitl` | `setup-wsl`, `mission`, `pattern`, `run`, `test`, `map download` | Virtual drone |
| `gcs` | `heartbeat`, `spray`, `monitor`, `listen`, `verify-statustext` | Radio + telemetry |
| `bringup` | `phase1`, `phase1-pi` | Hardware checklists |
| `calibrate` | `tune`, `validate`, `replay` | Depth calibration |
| `upload` | `test` | Photo upload smoke test |

```powershell
python tools\valiant.py --help
python tools\valiant.py sitl run config\sitl_missions\example_wall.yaml
```

**Do not run** `bench\verify_env.py`, `gcs\mission_monitor.py`, etc. directly - always use `valiant.py`.

---

## Dev checks

```powershell
.\tools\dev\verify_ps1.ps1
python tools\valiant.py env check
```

---

## Removed / relocated (use valiant instead)

| Old path | New |
|----------|-----|
| `tools\cv_bench_test.py` | `valiant bench cv` |
| `tools\deploy_to_pi.ps1` | `tools\deploy\deploy_to_pi.ps1` |
| `tools\create_github_issues.ps1` | `tools\dev\create_github_issues.ps1` |
