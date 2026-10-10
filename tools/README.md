# Valiant AEAC2027 tools

**New here?** Read [START_HERE.md](../START_HERE.md) first.

## One command to remember

```powershell
python tools\valiant.py guide
```

No arguments also prints the guide. First laptop setup: `pip install -e ..\valiant-mav` then `.\start.ps1`.

---

## Root scripts

| Script | When |
|--------|------|
| `valiant.py` | Setup, bench, SITL, survey, tagtrack, bringup |
| `setup.ps1` | First-time venv |
| `setup_wsl.ps1` | One-time WSL + ArduPilot |
| `launch_sitl.ps1` | Terminal 1 — legacy tcp:5760 SITL |
| `run_sitl_pattern.ps1` | GUIDED box pattern |
| `run_sitl_orbit.ps1` | GUIDED orbit |

---

## Subfolders

| Folder | Contents |
|--------|----------|
| `lib/` | `guide_text.py`, shared helpers |
| `sitl/` | launch bash, orbit/pattern Python, map download |
| `survey/` | Task 1 CLI (`run_survey.py`) |
| `tagtrack/` | Task 2 CLI (`run_tagtrack.py`) |
| `bench/` | `verify_env`, `diagnose`, safety bench |
| `gcs/` | heartbeat, monitor, STATUSTEXT verify, params |
| `bringup/` | phase1 PowerShell |
| `calibrate/` | depth/RGB calibration |
| `field/` | field orbit runner |
| `deploy/` | Pi deploy helpers |
| `dev/` | path audit, issue helpers |

---

## Pick your path

| You are… | Run |
|----------|-----|
| **Brand new laptop** | `pip install -e ..\valiant-mav` → `.\start.ps1` |
| **Check install** | `python tools\valiant.py quickstart` |
| **Something failed?** | `python tools\valiant.py diagnose` |
| **Survey / tagtrack dry-run** | `valiant survey --dry-run` / `tagtrack --dry-run` |
| **SITL motion** | `sim_vehicle` or `launch_sitl.ps1` → `sitl pattern` / `sitl orbit` |
| **First drone connect** | `python tools\valiant.py bringup phase1` |
| **Field orbit** | `python tools\valiant.py field orbit --gcs-ip <ip> --laps 1` |

Competition rules: [docs/conops-2027.md](../docs/conops-2027.md).
