# Git branches

This repo uses **two long-lived branches**. Pick the right one before you clone or checkout.

| Branch | Purpose | Who uses it |
|--------|---------|-------------|
| [`main`](https://github.com/Valiant-Aerotech/AEAC2027/tree/main) | Stable baseline after the AEAC 2026 rebase: fleet hardware docs, Task 1 (Vivi), repo scaffolding, team onboarding. **No Task 2 autonomy stack yet.** | Hardware, Task 1, docs-only work |
| [`onboard-pi`](https://github.com/Valiant-Aerotech/AEAC2027/tree/onboard-pi) | **Task 2 autonomy** (Vion GCS offload + Vivi companion path), **SITL simulation**, gimbal, metric recon, motion stack, runbooks. | Autonomy / CV / sim development |

## What lives only on `onboard-pi`

Roughly **83 files / ~6k lines** ahead of `main` (as of the SITL milestone), including:

- `src/valiant/autonomy/` — orchestrator, planner, spray, SITL motion/preflight
- `src/valiant/common/sitl_*.py`, `synthetic_target_camera.py`, `physics_synthetic_camera.py`
- `config/vion.yaml` — `flight_profiles.sitl`, `sitl_physics`, `vivi`
- `tools/launch_sitl.ps1`, `tools/run_sitl_mission.ps1`, `tools/sitl/`
- `tests/sitl/`, `tests/fixtures/sitl_*`
- `docs/runbooks/sitl-wsl.md`, field-test updates

`main` still has the shared skeleton (`missions/`, `config/`, `hardware/`, `tools/setup.ps1`) but not the closed-loop Task 2 pipeline.

## Recommended workflow

```powershell
# Autonomy or SITL work
git fetch origin
git checkout onboard-pi
git pull origin onboard-pi

# Hardware / Task 1 only (no autonomy)
git checkout main
git pull origin main
```

1. **Feature branches** branch off `onboard-pi` for autonomy/SITL (e.g. `onboard-pi-sitl-dashboard`).
2. Open PRs **into `onboard-pi`** for review.
3. When Task 2 is competition-ready, open one PR **`onboard-pi` → `main`** (do not force-push `main`).

## Virtual sim vs physical drone

| Environment | Branch | Connection | Camera |
|-------------|--------|------------|--------|
| **SITL (no drone)** | `onboard-pi` | `tcp:127.0.0.1:5760` | Synthetic / physics / video replay |
| **Hand-test (FC, props off)** | `onboard-pi` | `COM5` or UDP | scrcpy / webcam bench |
| **Field** | `onboard-pi` → `main` when merged | Radio COM | scrcpy |

Full SITL guide: [runbooks/sitl-overview.md](runbooks/sitl-overview.md).

## Commit history (onboard-pi autonomy arc)

| Commit | Summary |
|--------|---------|
| `507b2f8` | Full rebase after AEAC 2026 |
| `c93706b` | Team onboarding prep |
| `d04f209` | Vivi + Raspberry Pi companion path |
| `6f6d35f` | Gimbal configs and actuation |
| `91cde0a` | SITL mode (`--sitl`) |
| `4b939f0` | SITL home + map fixtures |
| `722fbd4` | Motion stack, dashboard, multi-target |
| `5929506` | Preflight, safety, remediation fixes |

Use `git log main..onboard-pi` for the full list.
