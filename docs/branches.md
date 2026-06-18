# Git branches

**Default branch: [`main`](https://github.com/Valiant-Aerotech/AEAC2027/tree/main)**. Clone and develop here.

As of June 2026, `main` includes the full AEAC2027 stack:

- Task 1 (Vivi survey)
- Task 2 autonomy (orchestrator, auto-nav, spray, upload)
- SITL simulation (ArduPilot + synthetic/physics cameras)
- Pi companion path (`hardware/vion/rpi/`)
- CV training scripts (`src/valiant/cv/`) and active runtime CV (`src/valiant/autonomy/cv/`)

## Long-lived branches

| Branch | Status | Notes |
|--------|--------|-------|
| **`main`** | **Primary** (all features integrated) | Day-to-day development target |
| `onboard-pi` | Synced with `main` | Historical name; kept for bookmarks - same tip as `main` |
| `feature/CV` | Merged into `main` | Task 2 CV scripts (PR #80); branch may receive occasional CV-only work |

## Recommended workflow

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
git pull origin main
```

1. **Feature branches** branch off `main` (e.g. `feature/sitl-tuning`, `fix/approach-gain`).
2. Open PRs **into `main`** for review.
3. Do not force-push `main`.

## Virtual sim vs physical drone

All modes below use **`main`**. Branch choice is no longer required.

| Environment | Connection | Camera | Entry |
|-------------|------------|--------|-------|
| **SITL (no drone)** | `tcp:127.0.0.1:5760` | Synthetic / physics / video | `.\tools\run_sitl_mission.ps1` |
| **Hand-test (FC, props off)** | `COM5` or UDP | scrcpy / webcam | `docs/runbooks/vivi-hand-test.md` |
| **Vivi bench (Pi)** | Pi UART | RPi camera + ToF | `hardware/vion/rpi/run_mission.py --profile vivi` |
| **Field (Vion)** | Radio COM | RPi camera | `hardware/vion/rpi/run_mission.py --profile indoor` |

Full SITL guide: [runbooks/sitl-overview.md](runbooks/sitl-overview.md).

## What merged into `main` (2026-06)

| Source | Contents |
|--------|----------|
| `metric-reconstruction` | ArduCam ToF drivers, depth-at-target metric recon |
| `feature/CV` | `src/valiant/cv/task2_cv_script.py`, `convolute_infer.py`, training notebook |
| `onboard-pi` | SITL motion stack, orchestrator, dashboard, gimbal, flight profiles |

Key merge commits: `dd0402c` (feature/CV → main), `9a4eb43` (onboard-pi + feature/CV integration).

## Repo map (on `main`)

```
src/valiant/autonomy/     # Task 2 pipeline (orchestrator, SITL, cv runtime)
src/valiant/cv/           # Standalone CV training / inference scripts
config/vion.yaml          # flight_profiles: sitl, sitl_physics, vivi
tools/launch_sitl.ps1     # WSL ArduPilot
tools/run_sitl_mission.ps1
tests/sitl/               # Integration tests (need SITL running)
```
