# AEAC2027

Valiant Aerotech competition software for AEAC 2027.

**New to the team?** Start with [WELCOME.md](WELCOME.md). Clone **`main`** - it has Task 1, Task 2 autonomy, SITL, and CV.

## Fleet

| Drone | Role | Mission |
|-------|------|---------|
| **Vulcan 2** | Heavy lifter (carries Vivi) | Hardware docs only - `hardware/vulcan2/` |
| **Vion** | Fire suppression (Pi companion + Pixhawk) | Task 2 - `hardware/vion/rpi/run_mission.py` |
| **Vivi** | Surveying drone | Task 1 - `missions/task1_vivi_survey.py` |

## First connect (hardware day)

| Machine | Run first |
|---------|-----------|
| GCS laptop + drone | `.\tools\bringup_gcs.ps1` |
| Raspberry Pi (SSH) | `bash hardware/vion/rpi/first_connect.sh` |

Full checklist: [docs/runbooks/vion-bringup.md](docs/runbooks/vion-bringup.md)

## Quick start (new GCS laptop)

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
.\tools\setup_gcs.ps1
python tools\verify_env.py
notepad config\vion.yaml    # set telemetry radio COM port
```

## Run a mission

**Primary (onboard Pi):**

```bash
python hardware/vion/rpi/run_mission.py --profile vivi
```

**GCS / dev:**

```powershell
python tools\mission_monitor.py
python missions\task2_vion_auto_extinguish.py      # Task 2 autonomous (field)
python missions\task2_vion_manual_photo.py         # Task 2 manual fallback
python missions\task1_vivi_survey.py               # Task 1 surveying
```

### Virtual drone (no hardware)

```powershell
.\tools\launch_sitl.ps1          # terminal 1 — ArduPilot in WSL
.\tools\run_sitl_mission.ps1     # terminal 2 — full mission + dashboard
```

[docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md)

## Repo layout

```
missions/          <- GCS entry points (dev / manual)
hardware/vion/rpi/ <- Pi primary flight entry
src/valiant/       <- library code
config/            <- per-drone YAML + vion_calibration.yaml
tools/             <- setup, bringup, monitor scripts
docs/runbooks/     <- vion-bringup.md, field-test-plan.md
models/            <- ONNX models (best.onnx)
```

See [WELCOME.md](WELCOME.md) for new members and [ONBOARDING.md](ONBOARDING.md) for full setup. See [docs/architecture.md](docs/architecture.md) for the modular pipeline design. **Branches:** [docs/branches.md](docs/branches.md). **SITL sim:** [docs/runbooks/sitl-overview.md](docs/runbooks/sitl-overview.md). Competition rules: [docs/conops.md](docs/conops.md).

**Before hardware:** [docs/runbooks/whats-left-before-hardware.md](docs/runbooks/whats-left-before-hardware.md)
