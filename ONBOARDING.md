# Onboarding - AEAC2027

New recruit? Start with [WELCOME.md](WELCOME.md).

## Which branch?

**Use `main`** for everything: Task 1, Task 2 autonomy, SITL, CV, and hardware docs are all integrated.

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
```

Details: [docs/branches.md](docs/branches.md).

Welcome. This guide gets you from a fresh Windows laptop to running a mission.

## Prerequisites

Install these **before** running setup:

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.10+ | Mission software | [python.org](https://www.python.org/downloads/) - check "Add to PATH" |
| Git | Clone this repo | [git-scm.com](https://git-scm.com/) |
| Mission Planner | MAVLink to Pixhawk | [ardupilot.org](https://ardupilot.org/planner/) |
| scrcpy | Phone camera mirror (Task 2 GCS path) | `winget install Genymobile.scrcpy` or [GitHub releases](https://github.com/Genymobile/scrcpy) |
| ADB | Android debug (wireless scrcpy) | Comes with scrcpy / Android SDK platform-tools |

## Setup (one time per laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
.\tools\setup.ps1
python tools\verify_env.py
```

## Configure for this machine

Edit the YAML for the drone you are flying. The most common change is the COM port:

```powershell
notepad config\vion.yaml
```

Set `mavlink.connection` to your telemetry COM port (e.g. `COM5`). Use `udpin:127.0.0.1:14550` for SITL or Mission Planner UDP forwarding.

## Run missions

| Mission | Command | Drone |
|---------|---------|-------|
| Task 2 auto extinguish | `python missions\task2_vion_auto_extinguish.py` | Vion |
| Task 2 manual photo | `python missions\task2_vion_manual_photo.py` | Vion |
| Task 1 survey | `python missions\task1_vivi_survey.py` | Vivi |

Add `--help` to any mission for options.

## Repo navigation

- **Run something?** → `missions/` or `hardware/vion/rpi/run_mission.py`
- **Change tuning?** → `config/vion.yaml`
- **Understand the pipeline?** → `docs/architecture.md`
- **FC parameters / Lua?** → `hardware/<drone>/`
- **Debug MAVLink?** → `python tools\mavproxy_listen.py`
- **SITL (no hardware)?** → [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md)

## Common issues

**`verify_env.py` fails on imports** - re-run `.\tools\setup.ps1`

**No COM port found** - plug in telemetry radio, check Device Manager, update `config/vion.yaml`

**scrcpy window not found** - ensure phone is connected; mission launches window titled `ExtinguisherCam`

**MAVLink heartbeat timeout** - open Mission Planner, confirm telemetry link, or use `--connection udpin:127.0.0.1:14550`

## Bench-test (no drone required)

```powershell
python tools\cv_bench_test.py --camera 0
python tools\metric_bench_test.py --camera 0
python tools\safety_bench_test.py
python tools\conops_check.py
python tools\cv_regression_test.py --video footage.mp4
python -m valiant.autonomy.cv.training.generate_targets --count 20
```

### Full virtual mission (SITL)

No Pixhawk, no COM port. Requires WSL + ArduPilot build (one-time):

```powershell
.\tools\launch_sitl.ps1          # terminal 1
.\tools\run_sitl_mission.ps1     # terminal 2
```

See [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md).

Tune purple/blue thresholds in `config/vion.yaml` under `cv.hsv_dry` and `cv.hsv_shot`. For distance tuning see `metric_recon` (FOV estimate) and `auto_nav` (approach speed, side clearance). Safety abort thresholds live under `safety` in the same file - see [docs/runbooks/task2-vion-auto.md](docs/runbooks/task2-vion-auto.md).

## Next steps for new members

1. Run `python tools\conops_check.py` (confirms CONOPS config loads)
2. Run SITL mission (above) for full state machine without hardware
3. Pick an issue from [GitHub](https://github.com/Valiant-Aerotech/AEAC2027/issues); see [WELCOME.md](WELCOME.md)
