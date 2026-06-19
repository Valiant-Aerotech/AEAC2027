# Architecture

Task 2 autonomy is a **modular pipeline**. Primary deployment runs on the **Vion Raspberry Pi companion**; GCS laptop is for calibration, monitor, and manual fallback.

## Pipeline (onboard RPi)

```
AI camera + ArduCam ToF (Pi)
        |
   CV module          -> CVPacket { dry: [(px,py)...], shot: [(px,py)...] }
        |
   Metric Recon       -> MetricPacket { slant/horizontal range, altitude_error_m, clearance }
        |                  geometry_3d.py: camera rays, gimbal pitch, depth bbox sampling
        |
   Auto-Nav           -> MAVLink velocity (GUIDED) — 3D vz from altitude_error on Pi;
        |                  SITL: ned_kinematics 3D vector + pixel lateral fine-tune
        |
   Spray Water        -> aim check (pixel + altitude alignment) -> SERVO15
        |
   Upload             -> Google Drive photo proof (or local copy)
```

Pixhawk 6C + Holybro H-Flow (DroneCAN) handle indoor hover stability. H-Flow is not used for extinguish aim.

## GCS role

- **Start here:** [START_HERE.md](../START_HERE.md) and `python tools/valiant.py guide`
- Unified tooling: `python tools/valiant.py` ([tools/README.md](../tools/README.md))
- Calibration: `valiant calibrate tune|validate|replay` (wraps `calibrate_depth_rgb.py`, etc.)
- Mission monitor: `valiant gcs monitor` (UDP, read-only)
- Legacy dev path: scrcpy + `missions/task2_vion_auto_extinguish.py`

## Repo mapping

| Module | Code path |
|--------|-----------|
| CV (runtime) | `src/valiant/autonomy/cv/` |
| CV (training scripts) | `src/valiant/cv/` (`task2_cv_script.py`, `convolute_infer.py`) |
| Metric Recon | `src/valiant/autonomy/metric_recon/` (+ `geometry_3d.py`) |
| NED kinematics (SITL + shared) | `src/valiant/common/ned_kinematics.py` |
| Auto-Nav | `src/valiant/autonomy/auto_nav/` |
| Flight modes | `src/valiant/autonomy/flight/` |
| Telemetry mirror | `src/valiant/autonomy/telemetry_bridge.py` |
| Spray Water | `src/valiant/autonomy/spray/` |
| Upload | `src/valiant/autonomy/upload/` |
| Orchestrator | `src/valiant/autonomy/orchestrator.py` |
| RPi entry | `hardware/vion/rpi/run_mission.py` |

## State machine (Task 2)

`SEARCHING -> APPROACHING -> AIMING -> FIRING -> VERIFYING -> CAPTURING -> UPLOADING -> SEARCHING (next target)`

Target loss during APPROACHING or AIMING reverts to SEARCHING. After UPLOADING, the orchestrator searches for the next target until the flight window ends or `--max-targets` is reached.

Competition rules are centralized in `config/conops.yaml` - see [docs/conops.md](conops.md).

## Task 1 (Vivi)

Separate pipeline in `src/valiant/task1/` - MAVLink telemetry, building survey, target report. No dependency on Task 2 modules.

## Config

Tunables in `config/vion.yaml` (and `config/vivi.yaml` for Task 1). Optional per-airframe `config/vion_calibration.yaml` (from `.example` template).

## SITL (virtual drone + environment)

The same orchestrator runs against **ArduPilot SITL** instead of hardware:

```
ArduPilot SITL (WSL)  ←── tcp:5760 ──→  orchestrator.py
                                              ↑
                         synthetic / physics / video camera
                         + JSON world (wall, targets, map)
                         + 3D NED motion (search/approach/altitude coupled)
```

| Component | Code |
|-----------|------|
| Mission loop + `--sitl` | `autonomy/orchestrator.py` |
| 3D motion | `common/ned_kinematics.py`, `sitl_motion.py`, `sitl_search.py` |
| Preflight | `sitl_preflight.py` |
| Cameras | `common/synthetic_target_camera.py`, `physics_synthetic_camera.py` |
| Dashboard | `cv/sitl_map_view.py` |
| Standalone CV scripts | `src/valiant/cv/task2_cv_script.py` |

Runbook: [runbooks/sitl-overview.md](runbooks/sitl-overview.md).
