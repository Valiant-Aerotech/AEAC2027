# Architecture

Task 2 autonomy is a **modular pipeline** running on the GCS laptop. Vion has no onboard computer - the laptop is the brain.

## Pipeline

```
Phone camera (DJI goggles → scrcpy)
        ↓
   CV module          → CVPacket { dry: [(px,py)...], shot: [(px,py)...] }
        ↓
   Metric Recon       → MetricPacket { pixel_offset, distance_m, wall_distance_m }
        ↓
   Auto-Nav           → MAVLink velocity commands (GUIDED mode)
        ↓
   Spray Water        → aim check → SERVO15 actuation
        ↓
   Upload             → Google Drive photo proof
```

## Repo mapping

| Module | Code path |
|--------|-----------|
| CV | `src/valiant/autonomy/cv/` |
| Metric Recon | `src/valiant/autonomy/metric_recon/` |
| Auto-Nav | `src/valiant/autonomy/auto_nav/` |
| Spray Water | `src/valiant/autonomy/spray/` |
| Upload | `src/valiant/autonomy/upload/` |
| Orchestrator | `src/valiant/autonomy/orchestrator.py` |

## State machine (Task 2)

`SEARCHING → APPROACHING → AIMING → FIRING → VERIFYING → CAPTURING → UPLOADING → SEARCHING (next target)`

Target loss during APPROACHING or AIMING reverts to SEARCHING. After UPLOADING, the orchestrator searches for the next target until the flight window ends or `--max-targets` is reached.

Competition rules are centralized in `config/conops.yaml` - see [docs/conops.md](conops.md).

## Task 1 (Vivi)

Separate pipeline in `src/valiant/task1/` - MAVLink telemetry, building survey, target report. No dependency on Task 2 modules.

## Config

All tunables live in `config/vion.yaml` (and `config/vivi.yaml` for Task 1). A new laptop only changes `mavlink.connection`.

## SITL (virtual drone + environment)

On branch **`onboard-pi`**, the same orchestrator runs against **ArduPilot SITL** instead of hardware:

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

Runbook: [runbooks/sitl-overview.md](runbooks/sitl-overview.md).
