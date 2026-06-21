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
4. Wait for **CI** (GitHub Actions) to pass on the PR.
5. Do not force-push `main`.

## Continuous integration (GitHub Actions)

Every push to `main` and every pull request into `main` runs [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) as **five parallel jobs** (duplicate runs on the same branch cancel in-progress via `concurrency`):

| Job | What it covers |
|-----|----------------|
| **Lint** | Ruff fatal checks (`E9`, `F63`, `F7`, `F82`) on `src/` and `tests/` |
| **Mavlink and safety** | Connection hints, STATUSTEXT, land, flight profiles, `safety.lua` preflight, SITL preflight parsing |
| **Motion and nav** | Planner fire gates, NED kinematics, GUIDED masks, pilot override, SITL motion/search/pattern/physics pose, GCS HUD |
| **CV and metric** | YOLO ONNX smoke, 3D metric geometry, synthetic camera, SITL physics |
| **Config and platform** | `rpas.yaml` / flight profiles, repo layout, upload naming, SITL mission loader, YAML smoke, `verify_env.py` |

[`.github/dependabot.yml`](../.github/dependabot.yml) opens monthly PRs for GitHub Actions and pip dependencies.

**Not in CI (run locally):**

- [`test_field_orbit.py`](../tests/test_field_orbit.py), [`test_guided_forward.py`](../tests/test_guided_forward.py) — field orbit experiments
- [`tests/sitl/`](../tests/sitl/) — live ArduPilot (`@pytest.mark.sitl`); start SITL with `.\tools\launch_sitl.ps1` then `.\tools\sitl\run_sitl_tests.ps1`
- `test_sitl_dashboard.py`, `test_synthetic_multi_camera.py` — optional sim/dashboard checks

### Run the same checks locally

```powershell
pip install -e ".[dev,cv]"
$env:PYTHONPATH = "src"

python -m ruff check src tests
python tools/bench/verify_env.py

python -m pytest tests/test_mavlink_connect.py tests/test_mavlink_statustext.py tests/test_mavlink_land.py tests/test_profile_connection.py tests/test_fc_safety.py tests/test_sitl_preflight.py -q

python -m pytest tests/test_motion_planner.py tests/test_ned_kinematics.py tests/test_visual_servo_guided.py tests/test_pilot_override.py tests/test_gcs_hud.py tests/test_sitl_motion.py tests/test_sitl_search.py tests/test_sitl_pattern.py tests/test_sitl_physics_pose.py -q

python -m pytest tests/test_yolo_onnx.py tests/test_metric_geometry_3d.py tests/test_synthetic_camera.py tests/test_sitl_physics.py -q

python -m pytest tests/test_rpas_config.py tests/test_flight_profiles.py tests/test_tools_layout.py tests/test_upload_drive.py tests/test_sitl_mission_loader.py tests/test_config_smoke.py -q
```

Orbit-only (local):

```powershell
python -m pytest tests/test_field_orbit.py tests/test_guided_forward.py -q
```

### Branch protection (repo admin, one-time)

In GitHub **Settings → Branches → Branch protection rules** for `main`:

1. Require a pull request before merging
2. Require status checks to pass → select all five: **Lint**, **Mavlink and safety**, **Motion and nav**, **CV and metric**, **Config and platform**

Live SITL integration stays manual until a separate nightly or `workflow_dispatch` job is added (Tier 3).

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
