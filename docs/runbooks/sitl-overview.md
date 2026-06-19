# SITL overview — virtual drone + environment

Software-in-the-loop (SITL) lets you run the **full Task 2 autonomy pipeline** on a laptop: state machine, MAVLink motion, CV, metric recon, spray gating, upload — **without a physical drone or radio**.

## What is simulated?

```
┌─────────────────────────────────────────────────────────────────┐
│  Windows — AEAC orchestrator (Python)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Camera sim   │  │ CV + metric  │  │ Auto-nav + motion stack│ │
│  │ (see below)  │→ │ recon        │→ │ → pymavlink velocities │ │
│  └──────────────┘  └──────────────┘  └───────────┬────────────┘ │
│         ▲                           dashboard    │ tcp:5760      │
│         │ pose-linked modes only                 ▼               │
│  ┌──────┴───────┐                    ┌────────────────────────┐ │
│  │ World JSON   │                    │ WSL — ArduPilot SITL     │ │
│  │ wall/targets │                    │ (virtual FC + dynamics)│ │
│  └──────────────┘                    └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

| Layer | Real hardware | SITL substitute |
|-------|---------------|-----------------|
| Flight controller | Pixhawk on drone | **ArduPilot SITL** in WSL (`sim_vehicle.py`) |
| Radio | COM / SiK telemetry | **TCP `127.0.0.1:5760`** |
| Camera | Phone → scrcpy | **Synthetic timeline**, **physics camera**, or **video file** |
| Targets / wall | Physical venue | **`tests/fixtures/sitl_*.json`** world + optional satellite map |
| Spray | SERVO15 | Disabled (`spray.method: none`) — jumps to CAPTURE for proof photo |

No COM port, no props, no phone required for the default sim profile.

## Two-terminal workflow (daily driver)

> **New to SITL?** Complete [START_HERE.md](../../START_HERE.md) setup first (`.\start.ps1`).

**Terminal 1 — virtual flight controller (WSL):**

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
.\tools\launch_sitl.ps1
```

Wait until ArduCopter shows `SERIAL0 on TCP port 5760`.

**Optional — Mission Planner:** TCP connect to `127.0.0.1:5762` (Valiant mission stays on 5760). See [sitl-wsl.md](sitl-wsl.md#mission-planner-as-gcs-viewer-optional).

**Terminal 2 — mission (Windows):**

```powershell
cd A:\Code\Valiant-Aerotech\AEAC2027
python tools\valiant.py sitl mission
```

Equivalent: `.\tools\run_sitl_mission.ps1`

This runs `missions/task2_vion_auto_extinguish.py --sitl --profile sitl` with:

- Preflight: EKF wait → GUIDED → arm → takeoff (~5 m)
- **Valiant SITL** OpenCV dashboard (FOV + wall side + top-down)
- Single-target suppress → upload → brief hold → COMPLETE

**Warm repeat** (SITL still running, already airborne):

```powershell
.\tools\run_sitl_mission.ps1 -SkipPreflight
```

Setup details and troubleshooting: [sitl-wsl.md](sitl-wsl.md).

## Camera / environment modes

Configured in `config/vion.yaml` under `flight_profiles`:

| Profile | Command | Camera | Environment | Best for |
|---------|---------|--------|-------------|----------|
| **`sitl`** (default) | `run_sitl_mission.ps1` | Timeline synthetic + world scene | JSON keyframes **linked to mavlink pose** | Fast mission logic, dashboard, single-target default |
| **`sitl_physics`** | `run_sitl_mission.ps1 -Physics` | Pose + gimbal projection | `sitl_physics_wall.json` | Geometry, approach tuning, harder CV |
| **Video replay** | `-Video path\to\clip.mp4` | Recorded footage | N/A | Regression from bench recordings |
| **Field** | `task2_vion_auto_extinguish.py` (no `--sitl`) | scrcpy | Real world | Competition |

Dashboard label: **`SIM`** = timeline synthetic, **`PHYSICS`** = pose-linked camera.

### Scenario files

| File | Role |
|------|------|
| `tests/fixtures/sitl_synthetic_multi.json` | Default world (2 targets in fixture; launcher uses `--max-targets 1`) |
| `tests/fixtures/sitl_physics_wall.json` | Single wall + targets for physics camera |
| `tests/fixtures/sitl_home.json` | SITL GPS home (map anchor) |
| `tests/fixtures/sitl_map/manifest.json` | Optional satellite top-down (`python tools/valiant.py sitl map download`) |

Override only when needed: `-Scenario tests\fixtures\sitl_approach_hard.json`

## Code map (SITL-specific)

```
src/valiant/autonomy/
  orchestrator.py          # --sitl, preflight, dashboard, state machine
  sitl_motion.py           # Backoff → Follow → Search → Hold → Reposition (3D NED)
  sitl_preflight.py        # EKF wait, GUIDED, arm, takeoff
  sitl_search.py           # 3D search creep, approach speed, altitude

src/valiant/common/
  ned_kinematics.py        # Rotation matrices, 3D velocity planning, VehiclePose
  sitl_physics.py          # Pose drain, target projection
  synthetic_target_camera.py   # Timeline + pose-linked keyframes
  physics_synthetic_camera.py  # Full pose-linked renderer
  sitl_map_asset.py        # Satellite crop for top-down

tools/
  valiant.py               # Unified CLI (bench, gcs, sitl, calibrate, conops)
  README.md                # Task → command index
  launch_sitl.ps1          # WSL ArduPilot launcher
  run_sitl_mission.ps1     # Thin wrapper → valiant sitl mission
  run_sitl_tests.ps1       # pytest SITL + motion unit tests
  sitl/launch_sitl.sh      # Called from WSL

tests/sitl/                # Integration tests (need SITL running)
tests/fixtures/sitl_*      # Worlds and timelines
```

Shared with field flight: `auto_nav/`, `metric_recon/`, `spray/`, `planner.py`, `approach_motion.py`.

Standalone CV training scripts live in `src/valiant/cv/` (merged from `feature/CV`).

## Orchestrator flags

| Flag | MAVLink | Motion | Camera |
|------|---------|--------|--------|
| *(default)* | Hardware COM/UDP | On | scrcpy |
| `--sitl` | `tcp:127.0.0.1:5760` | On | Profile (`sitl` / `sitl_physics`) |
| `--sim` | Optional | **Off** | As configured |
| `--hand-test` | Hardware | **Off** | scrcpy; gimbal + CV only |
| `--skip-sitl-preflight` | SITL | On | Skips arm/takeoff if already airborne |

## Tests

```powershell
python tools\valiant.py sitl test
# or: .\tools\run_sitl_tests.ps1

# 3D kinematics + metric geometry (no SITL)
python -m pytest tests/test_ned_kinematics.py tests/test_metric_geometry_3d.py -q
```

## Next improvements (optional)

- Hybrid profile: `--sitl` + scrcpy/YOLO for real CV against sim FC
- Ring-target HSV tuning from field photos in scenario colours
- Field validation on Vivi bench: confirm 3D metric recon vs tape measure on hardware
