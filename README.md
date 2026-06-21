# AEAC2027

Valiant Aerotech competition software for AEAC 2027.

**Never run this before?** → **[START_HERE.md](START_HERE.md)** (read this first)

**New team member?** → [WELCOME.md](WELCOME.md) → [ONBOARDING.md](ONBOARDING.md)

## Fleet

| Drone | Role | Mission |
|-------|------|---------|
| **Vulcan 2** | Heavy lifter (carries Vivi) | Hardware docs only - `hardware/vulcan2/` |
| **Vion** | Fire suppression (Pi + Pixhawk) | Task 2 - `hardware/vion/rpi/run_mission.py` |
| **Vivi** | Surveying drone | Task 1 - `missions/task1_vivi_survey.py` |

## Quick start (new laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
.\start.ps1
notepad config\rpas.yaml    # set telemetry COM port when you have a radio
python tools\valiant.py guide
```

## What to test

| Goal | Command |
|------|---------|
| Check install works | `python tools\valiant.py quickstart` |
| Test CV on webcam | `python tools\valiant.py bench cv --camera 0` |
| Run unit tests (same as CI) | See [docs/branches.md](docs/branches.md#continuous-integration-github-actions) — five jobs (lint, mavlink, motion, CV, config) |
| Virtual drone mission | `.\tools\setup_wsl.ps1` once, then `launch_sitl.ps1` + `valiant sitl mission` |
| First connect to drone | `python tools\valiant.py bringup phase1` |
| Fly on Pi (competition) | `python hardware/vion/rpi/run_mission.py --profile indoor --max-targets 1` |
| GCS telemetry HUD | `python tools\valiant.py gcs monitor` |

Full table: [START_HERE.md](START_HERE.md)

## First connect (hardware day)

| Machine | Run first |
|---------|-----------|
| GCS laptop | `python tools\valiant.py bringup phase1` |
| Raspberry Pi (SSH) | `bash hardware/vion/rpi/first_connect.sh` |

Checklist: [docs/runbooks/vion-bringup.md](docs/runbooks/vion-bringup.md)

## Repo layout

```
START_HERE.md      <- read first
missions/          <- GCS dev / manual entry points
hardware/vion/rpi/ <- Pi competition flight entry
src/valiant/       <- library code
config/            <- vion.yaml, conops, calibration
tools/valiant.py   <- one CLI for bench, SITL, bringup
docs/runbooks/     <- bringup, field test, SITL
models/            <- dry.onnx / best.onnx (gitignored; copy locally)
```

## More docs

- Architecture: [docs/architecture.md](docs/architecture.md)
- SITL sim: [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md)
- Before hardware: [docs/runbooks/whats-left-before-hardware.md](docs/runbooks/whats-left-before-hardware.md)
- Branches and CI: [docs/branches.md](docs/branches.md)
- Competition rules: [docs/conops.md](docs/conops.md)

**CI:** Pull requests into `main` run five GitHub Actions jobs (lint, mavlink, motion, CV, config). Field-orbit tests are local-only. See [docs/branches.md](docs/branches.md#continuous-integration-github-actions).
