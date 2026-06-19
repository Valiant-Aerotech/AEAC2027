# Onboarding - AEAC2027

**Start with [START_HERE.md](START_HERE.md)** if you have never run the repo.

New recruit overview: [WELCOME.md](WELCOME.md).

## Branch

Create a **feature branch** for every change. Do not commit directly to `main`.

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
git pull origin main
git checkout -b feature/your-name-topic
```

Details: [docs/branches.md](docs/branches.md).

## Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.10+ | Mission software |
| Git | Clone repo |
| Mission Planner | MAVLink to Pixhawk (hardware days) |
| scrcpy | Optional - GCS phone-camera dev path only |

## Setup (one time per laptop)

```powershell
.\start.ps1
```

Or manually: `.\tools\setup.ps1` then `python tools\valiant.py quickstart`.

## Configure this machine

```powershell
notepad config\rpas.yaml
```

Set `mavlink.connection` to your telemetry COM port (e.g. `COM5`). Airframe tuning lives in `config/vion.yaml` (inherited by RPAS). Skip until you connect a radio if you are only doing SITL/bench work.

## What to run (by scenario)

| Scenario | Command |
|----------|---------|
| **Forgot what to run** | `python tools\valiant.py guide` |
| **Health check** | `python tools\valiant.py quickstart` |
| **Webcam CV** | `python tools\valiant.py bench cv --camera 0` |
| **Virtual mission (SITL)** | [sitl-overview.md](docs/runbooks/sitl-overview.md) |
| **GCS + drone first connect** | `python tools\valiant.py bringup phase1` |
| **Pi first SSH** | `bash hardware/vion/rpi/first_connect.sh` |
| **Competition flight (Pi)** | `python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1` |
| **GCS monitor** | `python tools\valiant.py gcs monitor` |

### GCS dev missions (legacy / bench)

| Mission | Command |
|---------|---------|
| Task 2 auto (sim) | `python missions\task2_vion_auto_extinguish.py --sim --source webcam --camera 0` |
| Task 2 manual photo | `python missions\task2_vion_manual_photo.py --camera 0` |
| Task 1 survey | `python missions\task1_vivi_survey.py` |

**Competition autonomous runs on the Pi**, not these GCS scripts.

## Repo navigation

| Question | Where |
|----------|-------|
| What should I run? | `START_HERE.md` or `valiant guide` |
| Change tuning? | `config/rpas.yaml` (GCS) / `config/vion.yaml` (airframe) |
| Pipeline design? | `docs/architecture.md` |
| FC params / Lua? | `hardware/vion/` |
| Debug MAVLink? | `python tools\valiant.py gcs listen` |
| All tool commands? | [tools/README.md](tools/README.md) |

## Common issues

| Problem | Fix |
|---------|-----|
| Import errors | Re-run `.\start.ps1` |
| No COM port | Device Manager → update `config/rpas.yaml` |
| SITL won't connect | Run `launch_sitl.ps1` first; wait for port 5760 |
| Wrong entry point | Pi flight = `hardware/vion/rpi/run_mission.py` |

## Next steps

1. `python tools\valiant.py quickstart`
2. SITL mission - [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md)
3. Pick a GitHub issue - [WELCOME.md](WELCOME.md)

Tune CV in `config/vion.yaml` under `cv.hsv_dry` / `cv.hsv_shot`. Nav gains under `auto_nav`.
