# Git branches

**Default merge target:** [`main`](https://github.com/Valiant-Aerotech/AEAC2027/tree/main) on GitHub.

**Do not commit feature work directly to `main`.** Create a branch for every change set, open a PR into `main`, and merge after review.

## Recommended workflow

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
git pull origin main
git checkout -b feature/your-topic
```

1. Branch off latest `main` (examples: `feature/sitl-gcs-hud`, `fix/wsl-script-paths`, `docs/onboarding`).
2. Push your branch: `git push -u origin feature/your-topic`
3. Open a PR **into `main`** on GitHub.
4. Do not force-push `main`.

## What is on `main` today

As of June 2026, integrated stack includes:

- Task 1 (Vivi survey) and Task 2 autonomy (orchestrator, auto-nav, spray, upload)
- SITL simulation (ArduPilot, synthetic/physics cameras, 3D NED motion)
- SITL GCS HUD (`T2:` STATUSTEXT in Mission Planner Messages)
- SITL guided box pattern (`python tools\valiant.py sitl pattern`)
- Vivi GUIDED orbit (`python tools\valiant.py sitl orbit`, then field runbook)
- 3D metric reconstruction and unified CLI (`tools/valiant.py`)
- Pi companion path (`hardware/vion/rpi/`)

## Long-lived branches (historical)

| Branch | Status | Notes |
|--------|--------|-------|
| **`main`** | Primary merge target | Protected workflow: PRs only |
| `onboard-pi` | Synced with `main` | Historical bookmark |
| `feature/CV` | Merged into `main` | Occasional CV-only work may still branch from `main` |

## Sim vs hardware (same repo, any feature branch)

These modes are config/profile choices, not separate git branches:

| Environment | Connection | Camera | Entry |
|-------------|------------|--------|-------|
| **SITL (no drone)** | `tcp:127.0.0.1:5760` | Synthetic / physics / video | `python tools/valiant.py sitl mission` |
| **SITL pattern (no CV)** | `tcp:127.0.0.1:5760` | None (GUIDED legs only) | `python tools/valiant.py sitl pattern` |
| **SITL orbit (no CV)** | `tcp:127.0.0.1:5760` | None (field orbit geometry) | `python tools/valiant.py sitl orbit` |
| **Hand-test (FC, props off)** | `COM5` or UDP | scrcpy / webcam | `docs/runbooks/vivi-hand-test.md` |
| **Vivi bench (Pi)** | Pi UART | RPi camera + ToF | `hardware/vion/rpi/run_mission.py --profile vivi` |
| **Field (Vion)** | Radio COM | RPi camera | `hardware/vion/rpi/run_mission.py --profile indoor` |

Full SITL guide: [runbooks/sitl-overview.md](runbooks/sitl-overview.md).

## Repo map

```
src/valiant/autonomy/     # Task 2 pipeline (orchestrator, SITL, cv runtime)
src/valiant/autonomy/gcs_hud.py
src/valiant/autonomy/sitl_pattern.py
src/valiant/common/       # ned_kinematics.py, mavlink.py
config/rpas.yaml          # default platform (inherits config/vion.yaml)
config/vion.yaml          # flight_profiles: sitl, sitl_physics, vivi
config/sitl_missions/     # YAML experiments (example_wall, pattern_box)
tools/valiant.py          # Unified CLI
tools/launch_sitl.ps1
tools/run_sitl_pattern.ps1
tests/sitl/               # Integration tests (need SITL running)
```
