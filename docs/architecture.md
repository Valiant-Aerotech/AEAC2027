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
| CV | `src/valiant/autonomy/cv/` |
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

Tunables in `config/vion.yaml` plus per-airframe `config/vion_calibration.yaml` (from `.example` template).
