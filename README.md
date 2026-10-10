# AEAC2027

Valiant Aerotech competition software for AEAC 2027 (wildlife survey + tag & track).

Flight I/O lives in the sibling repo
[`valiant-mav`](https://github.com/Valiant-Aerotech/valiant-mav). **Install that first**, then this package.

**Never run this before?** → **[START_HERE.md](START_HERE.md)**

**New team member?** → [WELCOME.md](WELCOME.md) → [ONBOARDING.md](ONBOARDING.md)

## Fleet

| Aircraft | Role | Software |
|----------|------|----------|
| **Vivi** | Task 1 survey | `python tools/valiant.py survey` |
| **Vion** | Task 2 tag & track | `python tools/valiant.py tagtrack` |
| **Vulcan 2** | Heavy lifter | Hardware docs in `hardware/vulcan2/` |

## Quick start (new laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
pip install -e ..\valiant-mav
.\start.ps1
python tools\valiant.py guide
```

Copy `.env.example` to `.env` only if you need a competition token. Leave `AEAC_COMP_LIVE=0` (loopback) until a scored window.

## What to test

| Goal | Command |
|------|---------|
| Check install | `python tools\valiant.py quickstart` |
| Survey math (offline) | `python -m pytest tests/test_survey_math.py -q` |
| SITL motion (pattern / orbit) | `sim_vehicle` or `.\tools\launch_sitl.ps1`, then `valiant sitl pattern` / `sitl orbit` |
| Survey dry-run | `python tools\valiant.py survey --dry-run` |
| Tagtrack dry-run | `python tools\valiant.py tagtrack --dry-run` |
| First connect to drone | `python tools\valiant.py bringup phase1` |
| Field orbit (no CV) | `python tools\valiant.py field orbit --gcs-ip <ip> --laps 1` |
| GCS HUD | `python tools\valiant.py gcs monitor` |

## Repo layout

```
START_HERE.md              <- read first
src/valiant/missions/      <- Task 1 survey + Task 2 tagtrack (scoring lives here)
src/valiant/perception/    <- YOLO, ToF, geometry (no scoring clocks)
src/valiant/comms/         <- competition 1 Hz + GCS HUD
src/valiant/core/          <- re-exports valiant-mav + advisory safety
config/                    <- defaults.yaml, boundary poly, SITL overlays
tools/valiant.py           <- one CLI
docs/conops-2027.md        <- competition rules map
reference/                 <- inert 2026 study copies (not flown)
```

## More docs

- Competition rules: [docs/conops-2027.md](docs/conops-2027.md)
- Lessons: [docs/lessons-learned.md](docs/lessons-learned.md)
- SITL: [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md) · [sitl-wsl.md](docs/runbooks/sitl-wsl.md)
- Pi / bringup: [docs/runbooks/pi-fresh-install.md](docs/runbooks/pi-fresh-install.md) · [vion-bringup.md](docs/runbooks/vion-bringup.md)
- Branches and CI: [docs/branches.md](docs/branches.md)
