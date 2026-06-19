# Module Interfaces

Data contracts between autonomy modules. Implemented in `src/valiant/autonomy/packets.py`.

## TargetHit

Single detection with geometry:

```python
@dataclass
class TargetHit:
    cx: int
    cy: int
    area: int
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2
    confidence: float
```

## CVPacket (CV -> Metric Recon)

```python
@dataclass
class CVPacket:
    dry: list[TargetHit]    # un-extinguished purple targets
    shot: list[TargetHit]   # extinguished blue/wetted targets
    timestamp: float
    frame_id: int
    method: str             # hsv, yolo, both, hsv_fallback
```

- `dry` - targets still needing extinguishing (orchestrator tracks `primary_dry`)
- `shot` - already wetted targets (proof state, not used for navigation yet)
- Auto-Nav should consume MetricPacket, not CVPacket directly

## MetricPacket (Metric Recon -> Auto-Nav)

Built by `MetricReconstructor` from `CVPacket` + frame geometry + gimbal pitch + optional depth at target pixel, vehicle pose (SITL), and VL53L1X MAVLink.

| Field | Meaning |
|-------|---------|
| `pixel_offset` | Target centre vs frame centre |
| `distance_m` | **Planner-facing horizontal range** (falls back to slant when decomposition unavailable) |
| `slant_range_m` | Raw measured range along camera ray |
| `horizontal_range_m` | Ground-plane range from slant + ray elevation |
| `elevation_deg` / `azimuth_deg` | Target bearing from camera boresight |
| `altitude_error_m` | Signed vertical miss (+ = climb needed); used for onboard vz and fire gate |
| `vertical_clearance_m` | Vertical margin in image (mirror of side clearance) |
| `distance_min_m` / `distance_max_m` | FOV band when target size unknown |
| `distance_source` | `depth_at_target`, `fov_band`, `vl53l1x`, or empty |
| `wall_distance_m` | Horizontal range + wall offset |
| `side_clearance_m` | Lateral margin from frame edge + range |

Use `metric.planner_range_m()` for fire/approach gating (prefers `horizontal_range_m`).

3D geometry: `src/valiant/autonomy/metric_recon/geometry_3d.py`. SITL motion uses `src/valiant/common/ned_kinematics.py` (rotation matrices, 3D velocity toward goal).

## CV detection methods (`config/vion.yaml`)

| method | Behaviour |
|--------|-----------|
| `hsv` | Purple/blue HSV only - no ONNX required |
| `yolo` | `models/best.onnx` for dry (center 224x224 crop); HSV for shot confirm only |
| `both` | HSV for dry+shot first; YOLO supplements dry if HSV finds nothing |

Model path: `cv.models.dry` (default `models/best.onnx`). Inference via onnxruntime. Input size: `cv.yolo_input_size` (default 320, read from ONNX when possible).

Tune `hsv_dry` / `hsv_shot` / `hsv_min_area_px` for outdoor lighting.

## Bench test

Use the unified CLI ([tools/README.md](../tools/README.md)):

```powershell
python tools\valiant.py bench cv --camera 0
python tools\valiant.py bench metric --camera 0
python tools\valiant.py bench cv --regression --video footage.mp4
python tools\valiant.py conops check
```

Legacy direct scripts (`tools/cv_bench_test.py`, etc.) still work.

## Auto-Nav and Spray (`config/vion.yaml`)

- `metric_recon.mode`: `depth_at_target` (Pi) or `rangefinder` (GCS dev)
- `metric_recon.rangefinder`: `fov_estimate`, `vl53l1x`, or `none`
- `metric_recon.alt_align_tolerance_m`: block fire until altitude aligned (~0.25 m)
- `metric_recon.altitude_kp`: onboard vz from `altitude_error_m`
- `metric_recon.min_approach_distance_m`: CONOPS 2 m approach validation
- `metric_recon.fire_distance_m`: switch from APPROACHING to AIMING
- `auto_nav.lateral_pixel_blend`: pixel PD weight for lateral fine-tune (world-primary 3D motion)
- `auto_nav.side_clearance_m`: abort if target too close to frame edge
- `sitl.alt_align_tolerance_m`: same gate in SITL (uses scene + metric)

SITL motion: 3D NED velocity toward target (`ned_kinematics.velocity_toward_goal`); pixel servo fine-tunes lateral only.

## Safety (`config/vion.yaml`)

`SafetyMonitor` runs each orchestrator loop iteration:

| Check | Config | Action |
|-------|--------|--------|
| Battery | `safety.min_battery_pct` | Mission abort via `SYS_STATUS.battery_remaining` |
| Geofence | `safety.geofence_abort` | Mission abort via `FENCE_STATUS` or STATUSTEXT |
| Mission timeout | `safety.mission_timeout_s` | Mission abort after elapsed seconds |
| RTL on abort | `safety.rtl_on_abort` | Optional `MAV_CMD_NAV_RETURN_TO_LAUNCH` |

Target-loss and phase timeouts remain orchestrator-local (return to SEARCHING, not full abort).

## CONOPS (`config/conops.yaml`)

Competition rules are data, not hardcoded. `load_config()` merges `conops.yaml` and applies task2 limits into `metric_recon`. Helpers live in `src/valiant/autonomy/conops.py`.

- Photo names: `Task_2_{team}_target_{n}.jpg`
- Multi-target loop after each upload
- `VERIFYING` state waits for shot (blue) detection before capture

Run `python tools\valiant.py conops check` after editing rules. See [docs/conops.md](conops.md).

## Upload (`config/defaults.yaml`)

- `upload.method`: `local_copy` (default) or `gdrive_service_account`
- `upload.retry_count` / `upload.retry_delay_s`: retry failed uploads
- Credentials: `config/gdrive_credentials.json` (gitignored) + `upload.folder_id`
