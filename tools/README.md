# Valiant AEAC2027 tools

**New here?** Read [START_HERE.md](../START_HERE.md) first — not this file.

## One command to remember

```powershell
python tools\valiant.py guide
```

No arguments also prints the guide. First laptop setup: `.\start.ps1` from repo root.

---

## Pick your path

| You are… | Run |
|----------|-----|
| **Brand new laptop** | `.\start.ps1` |
| **Check install (no drone)** | `python tools\valiant.py quickstart` |
| **Webcam / CV test** | `python tools\valiant.py bench cv --camera 0` |
| **Virtual full mission** | Terminal 1: `.\tools\launch_sitl.ps1` → Terminal 2: `python tools\valiant.py sitl mission` |
| **First drone connect (GCS)** | `python tools\valiant.py bringup phase1` |
| **Telemetry HUD** | `python tools\valiant.py gcs monitor` |
| **Deploy to Pi** | `.\tools\deploy_to_pi.ps1 -PiHost user@ip` |

---

## CLI reference

| Group | Commands | Purpose |
|-------|----------|---------|
| *(top)* | `guide`, `quickstart`, `setup` | Scenario menu, health checks, venv install |
| `env` | `check` | Python packages |
| `conops` | `check` | Competition config |
| `bench` | `cv`, `metric`, `safety`, `smoke` | Laptop tests (no drone) |
| `sitl` | `mission`, `test`, `map download` | Virtual drone |
| `gcs` | `heartbeat`, `spray`, `monitor`, `listen` | Radio + telemetry |
| `bringup` | `phase1`, `phase1-pi` | Hardware checklists |
| `calibrate` | `tune`, `validate`, `replay` | Depth calibration |
| `upload` | `test` | Photo upload smoke test |

```powershell
python tools\valiant.py --help
```

**Do not run** `tools\verify_env.py`, `mission_monitor.py`, etc. directly — always use `valiant.py`.

---

## PowerShell helpers (called by CLI or docs)

| Script | When to use |
|--------|-------------|
| `setup.ps1` | First-time venv (`valiant setup`) |
| `launch_sitl.ps1` | Terminal 1 before SITL mission |
| `run_sitl_mission.ps1` | Used internally by `valiant sitl mission` |
| `bringup_gcs.ps1` | Extended first-connect (after `bringup phase1`) |
| `deploy_to_pi.ps1` | Copy repo + model to Pi |
| `webcam_bench.ps1` | Same as `valiant quickstart` + hints |

---

## Removed scripts (use valiant instead)

| Old | New |
|-----|-----|
| `setup_gcs.ps1` | `start.ps1` + `valiant bringup phase1` |
| `yolo_webcam_test.py` | `valiant bench cv` |
| `cv_regression_test.py` | `valiant bench cv --regression --video …` |
| `run_monitor.ps1` | `valiant gcs monitor` |
