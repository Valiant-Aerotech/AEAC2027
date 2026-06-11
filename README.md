# AEAC2027

Valiant Aerotech competition software for AEAC 2027. Everything in this repo is designed to run on a **fresh GCS laptop** with minimal setup.

**New to the team?** Start with [WELCOME.md](WELCOME.md), then open [GitHub Issues](https://github.com/Valiant-Aerotech/AEAC2027/issues).

## Fleet

| Drone | Role | Mission |
|-------|------|---------|
| **Vulcan 2** | Heavy lifter (carries Vivi) | Hardware docs only - `hardware/vulcan2/` |
| **Vion** | Fire suppression (GCS offload) | Task 2 auto + manual - `missions/task2_vion_*.py` |
| **Vivi** | Surveying drone | Task 1 target report - `missions/task1_vivi_survey.py` |

## Quick start (new laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
.\tools\setup.ps1
python tools\verify_env.py
notepad config\vion.yaml    # set your COM port
```

## Run a mission

```powershell
python missions\task2_vion_auto_extinguish.py      # Task 2 autonomous
python missions\task2_vion_manual_photo.py         # Task 2 manual fallback
python missions\task1_vivi_survey.py               # Task 1 surveying
```

## Repo layout

```
missions/          ← only files you run
src/valiant/       ← library code (never run directly)
config/            ← per-drone YAML (edit per laptop)
hardware/          ← FC params, Lua scripts per drone
tools/             ← setup and verify scripts
docs/              ← architecture, runbooks, interfaces
models/            ← ONNX models (see models/README.md)
```

See [WELCOME.md](WELCOME.md) for new members and [ONBOARDING.md](ONBOARDING.md) for full setup. See [docs/architecture.md](docs/architecture.md) for the modular pipeline design. Competition rules map to config in [docs/conops.md](docs/conops.md).
