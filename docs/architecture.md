# Architecture

Task 2 autonomy is a **modular pipeline**. Primary deployment runs on the **Vion Raspberry Pi companion**; GCS laptop is for calibration, monitor, and manual fallback.

## Pipeline (onboard RPi)

```
AI camera + ArduCam ToF (Pi)
        |
   CV module          -> CVPacket { dry: [(px,py)...], shot: [(px,py)...] }
        |
   Metric Recon       -> MetricPacket { pixel_offset, distance_m, distance_source }
        |                  depth_at_target: ToF sample at target pixel
        |
   Auto-Nav           -> MAVLink velocity (GUIDED or GUIDED_NOGPS)
        |
   Spray Water        -> aim check -> SERVO15 actuation
        |
   Upload             -> Google Drive photo proof (or local copy)
```

Pixhawk 6C + Holybro H-Flow (DroneCAN) handle indoor hover stability. H-Flow is not used for extinguish aim.

## GCS role

- Calibration and replay (`tools/calibrate_depth_rgb.py`, `tools/validate_calibration.py`)
- Mission monitor over UDP (`tools/mission_monitor.py`) - read-only, link loss does not abort mission
- Legacy dev path: scrcpy + `missions/task2_vion_auto_extinguish.py`

## Repo mapping

| Module | Code path |
|--------|-----------|
| CV (runtime) | `src/valiant/autonomy/cv/` |
| CV (training scripts) | `src/valiant/cv/` (`task2_cv_script.py`, `convolute_infer.py`) |
| CV (archive) | `src/valiant/autonomy/cv-archive/` (pre-merge reference) |
| Metric Recon | `src/valiant/autonomy/metric_recon/` |
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
```

| Component | Code |
|-----------|------|
| Mission loop + `--sitl` | `autonomy/orchestrator.py` |
| Motion / preflight | `sitl_motion.py`, `sitl_preflight.py` |
| Cameras | `common/synthetic_target_camera.py`, `physics_synthetic_camera.py` |
| Dashboard | `cv/sitl_map_view.py` |
| Standalone CV scripts | `src/valiant/cv/task2_cv_script.py` |

Runbook: [runbooks/sitl-overview.md](runbooks/sitl-overview.md).
