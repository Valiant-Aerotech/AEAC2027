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
| Sibling [`valiant-mav`](https://github.com/Valiant-Aerotech/valiant-mav) | Flight I/O (`pip install -e ../valiant-mav`) |
| Git | Clone repo |
| Mission Planner | MAVLink to Pixhawk (hardware days) |

## Setup (one time per laptop)

```powershell
pip install -e ..\valiant-mav
.\start.ps1
```

Or: `.\tools\setup.ps1` then `python tools\valiant.py quickstart`.

## What to run (by scenario)

| Scenario | Command |
|----------|---------|
| **Forgot what to run** | `python tools\valiant.py guide` |
| **Health check** | `python tools\valiant.py quickstart` |
| **Survey math** | `python -m pytest tests/test_survey_math.py -q` |
| **Survey / tagtrack dry-run** | `python tools\valiant.py survey --dry-run` / `tagtrack --dry-run` |
| **SITL motion** | [sitl-overview.md](docs/runbooks/sitl-overview.md) → `sitl pattern` / `sitl orbit` |
| **GCS + drone first connect** | `python tools\valiant.py bringup phase1` |
| **Pi first SSH** | `bash hardware/vion/rpi/first_connect.sh` — [pi-fresh-install.md](docs/runbooks/pi-fresh-install.md) |
| **Field orbit** | `python tools\valiant.py field orbit --gcs-ip <ip> --laps 1` |
| **GCS monitor** | `python tools\valiant.py gcs monitor` |

## Layering (do not blur)

| Package | Owns |
|---------|------|
| `missions/survey`, `missions/tagtrack` | Scoring clocks, 10 m clusters, reports, track CSV |
| `perception/` | Labels, boxes, optional `Detection.text` |
| `comms/competition/` | 1 Hz HTTP + penalty counters |
| `valiant-mav` | Connect, GUIDED hold, orbit, waypoints |

`reference/` is inert 2026 code for study only.

## Competition

Rules map: [docs/conops-2027.md](docs/conops-2027.md). Leave `AEAC_COMP_LIVE=0` until a scored window.
