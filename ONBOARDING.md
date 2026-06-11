# Onboarding - AEAC2027

New recruit? Start with [WELCOME.md](WELCOME.md).

Welcome. This guide gets you from a fresh Windows laptop to running a mission.

## Prerequisites

Install these **before** running setup:

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.10+ | Mission software | [python.org](https://www.python.org/downloads/) - check "Add to PATH" |
| Git | Clone this repo | [git-scm.com](https://git-scm.com/) |
| Mission Planner | MAVLink to Pixhawk | [ardupilot.org](https://ardupilot.org/planner/) |
| scrcpy | Phone camera mirror (Task 2) | `winget install Genymobile.scrcpy` or [GitHub releases](https://github.com/Genymobile/scrcpy) |
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

- **Run something?** → `missions/`
- **Change tuning?** → `config/`
- **Understand the pipeline?** → `docs/architecture.md`
- **FC parameters / Lua?** → `hardware/<drone>/`
- **Debug MAVLink?** → `python tools\mavproxy_listen.py`

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

Tune purple/blue thresholds in `config/vion.yaml` under `cv.hsv_dry` and `cv.hsv_shot`. For distance tuning see `metric_recon` (FOV estimate) and `auto_nav` (approach speed, side clearance). Safety abort thresholds live under `safety` in the same file - see [docs/runbooks/task2-vion-auto.md](docs/runbooks/task2-vion-auto.md).

## Next steps for new members

1. Read [docs/drones.md](docs/drones.md) - know which drone does what
2. Read [docs/architecture.md](docs/architecture.md) - CV -> Metric Recon -> Auto-Nav pipeline
3. Read [docs/interfaces.md](docs/interfaces.md) - CVPacket, MetricPacket, and detection methods
4. Read [docs/runbooks/field-test-plan.md](docs/runbooks/field-test-plan.md) - phased validation checklist
5. Pick a GitHub issue from the [issue board](https://github.com/Valiant-Aerotech/AEAC2027/issues) (see [docs/github-issues-backlog.md](docs/github-issues-backlog.md))
