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
    debug: dict | None = None   # optional e.g. {"dry_backend": "subframe"}
```

- `dry` - targets still needing extinguishing (orchestrator tracks `primary_dry`)
- `shot` - already wetted targets (proof state, not used for navigation yet)
- Auto-Nav should consume MetricPacket, not CVPacket directly

## MetricPacket (Metric Recon -> Auto-Nav)

Built by `MetricReconstructor` from `CVPacket` + frame geometry + gimbal pitch + optional depth at target pixel, vehicle pose (SITL), and VL53L1X MAVLink.

| Field | Meaning |
|-------|---------|
| `pixel_offset` | Servo aim centre vs frame centre (from `aim_px` when set, else `target_px`) |
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
| `aim_px` | Virtual servo aim point for edge targets; `None` uses `target_px` |
| `target_offset` | Detected target centre vs frame centre (spray gate) |
| `edge_proximity` | `EdgeProximity(left, right, top, bottom)` — which frame edges are near |
| `corner_target` | Property: `edge_proximity.lateral` (legacy) |
| `lateral_clearance_ok` / `vertical_clearance_ok` | Per-axis geometric offset satisfied |
| `body_clearance_ok` | Property: both axis OK flags |
| `body_alt_bias_m` | Gimbal-mode vertical body shift (+ = hold higher; floor edge) |
| `lateral_clearance_m` | Optional ToF depth-jump hint on open lateral side |
| `vertical_open_clearance_m` | Optional ToF depth-jump on open vertical side |

**Dual alignment (edge targets):** `pixel_offset` is computed from `aim_px` when set (body/servo). Spray gating uses `target_offset` via `is_target_aligned()`; body hold uses `is_body_aligned()`. Gimbal pitch tracks detected `hit.cy`; vertical body uses `body_alt_bias_m` in `_metric_vz_ned`. Camera-down mode uses full `servo_px` including vertical aim.

**Edge config (`metric_recon`):** `corner_edge_frac` / `edge_edge_frac`, `corner_min_bbox_area_px`, `body_half_width_m`, `clearance_margin_m`, `body_half_height_m`, `vertical_clearance_margin_m`, `lateral_sample_offset_px`, `vertical_sample_offset_px`, `lateral_depth_jump_min_m`. **Auto-nav:** `spray_deadband_px`, `spray_vertical_deadband_px`, `vertical_clearance_m`, `side_clearance_m`.

Use `metric.planner_range_m()` for fire/approach gating (prefers `horizontal_range_m`).

3D geometry: `src/valiant/autonomy/metric_recon/geometry_3d.py`. SITL motion uses `src/valiant/common/ned_kinematics.py` (rotation matrices, 3D velocity toward goal).

## CV detection methods (`config/rpas.yaml` / `config/vion.yaml`)

Airframe tuning lives in `config/vion.yaml`; default platform loads via `config/rpas.yaml`.

| method | Behaviour |
|--------|-----------|
| `hsv` | Purple/blue HSV only - no ONNX required |
| `yolo` | `models/best.onnx` for dry via 294px spiral subframes; HSV for shot confirm only |
| `both` | HSV for dry+shot first; YOLO supplements dry if HSV finds nothing |

Model path: `cv.models.dry` (default `models/best.onnx`). Inference via onnxruntime.

Subframe settings (`config/vion.yaml`): `cv.inference_mode` (`subframe` | `center_crop`), `cv.subframe_size` (default 294), `cv.max_subframes`, `cv.edge_margin`, `cv.nms_threshold`. Legacy center crop uses 224px when `inference_mode: center_crop`.

Tune `hsv_dry` / `hsv_shot` / `hsv_min_area_px` for outdoor lighting.

## CV public API (`valiant.autonomy.cv`)

External code (orchestrator, bench tools, calibrate scripts) should import only:

| Symbol | Purpose |
|--------|---------|
| `create_target_detector(cfg)` | Factory for `TargetDetector` |
| `TargetDetector.detect(frame)` | Returns `CVPacket` with full-frame pixel coords |
| `draw_mission_overlay(frame, packet, state, cfg, ...)` | HUD; reads `cv.*` from cfg internally |
| `hits_to_bench_dict(hits)` | Bench dict format for `getTargets()` |
| `resolve_dry_model_path(cfg)` | Locate dry ONNX/PT weights |
| `crop_preview_for_display(frame, cfg)` | Display-only grid crop (bench) |

Do **not** import `subframe_grid`, `subframe_yolo`, `yolo_onnx`, or `dry_detector` from orchestrator, metric recon, or auto-nav.

## Metric recon public API (`valiant.autonomy.metric_recon`)

| Symbol | Purpose |
|--------|---------|
| `create_metric_reconstructor(master, cfg, *, sim=False)` | Factory for `MetricReconstructor` |
| `MetricReconstructor.reconstruct(cv_packet, w, h, ...)` | Returns `MetricPacket` |
| `InlineDepthSource` / `RecordingDepthSource` | Bench/replay depth providers (calibrate tools) |
| `metric_vz_from_altitude_error(...)` | Onboard vz from `altitude_error_m` (orchestrator helper) |

Do **not** import `corner_target`, `aim_offset`, `geometry_3d`, or `reconstructor` from orchestrator or auto-nav. Corner logic stays inside metric recon.

## Auto-nav public API (`valiant.autonomy.auto_nav`)

| Symbol | Purpose |
|--------|---------|
| `create_motion_planner(cfg)` | Approach/aim/fire gating from `MetricPacket` |
| `create_mavlink_driver(master, cfg)` | Visual-servo velocity commands |
| `MotionIntent` | `APPROACH`, `HOLD_AIM`, `ABORT` |
| `effective_approach_speed(cfg, metric, ...)` | Tapered forward speed during approach |

Orchestrator consumes `MetricPacket` only; use `metric.servo_px` for the lateral servo point (virtual aim when corner offset is active).

Do **not** import `visual_servo`, `mavlink_driver`, or `planner` directly from orchestrator.

## Spray public API (`valiant.autonomy.spray`)

| Symbol | Purpose |
|--------|---------|
| `is_body_aligned(metric, cfg)` | Servo/aim offset within deadband |
| `is_target_aligned(metric, cfg)` | Detected target within spray deadband |
| `is_aimed(metric, cfg)` | Both alignments + altitude tolerance |
| `create_water_trigger(mav, cfg)` | MAVLink servo or GPIO spray actuation |

### Allowed imports by subsystem

| Module | May import from CV | May import from metric_recon | May import from auto_nav | May import from spray |
|--------|-------------------|------------------------------|--------------------------|----------------------|
| `orchestrator` | `valiant.autonomy.cv`, `exceptions` | `valiant.autonomy.metric_recon` | `valiant.autonomy.auto_nav` | `valiant.autonomy.spray` |
| `metric_recon` | — | internal only | — | — |
| `auto_nav` | — | `valiant.autonomy.packets` only | internal; `spray` public API | `valiant.autonomy.spray` |
| Bench / calibrate tools | `valiant.autonomy.cv` | `valiant.autonomy.metric_recon` | — | — |

## Bench test

Use the unified CLI ([tools/README.md](../tools/README.md)):

```powershell
python tools\valiant.py bench cv --camera 0
python tools\valiant.py bench metric --camera 0
python tools\valiant.py bench cv --regression --video footage.mp4
python tools\valiant.py conops check
```

Legacy direct scripts were removed; use `python tools\valiant.py` subcommands only.

## Auto-Nav and Spray (`config/vion.yaml`, inherited by `config/rpas.yaml`)

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

## Safety (`config/vion.yaml`, inherited by `config/rpas.yaml`)

`SafetyMonitor` runs each orchestrator loop iteration:

| Check | Config | Action |
|-------|--------|--------|
| Battery | `safety.min_battery_pct` | Mission abort via `SYS_STATUS.battery_remaining` |
| Geofence | `safety.geofence_abort` | Mission abort via `FENCE_STATUS` or STATUSTEXT |
| Mission timeout | `safety.mission_timeout_s` | Mission abort after elapsed seconds |
| RTL on abort | `safety.rtl_on_abort` | Optional `MAV_CMD_NAV_RETURN_TO_LAUNCH` |
| Lua kill script | `safety.require_lua_safety` | Block field flight if `SCR_ENABLE` off or `safety.lua` missing |
| Lua script name | `safety.lua_safety_script` | Default `safety.lua` on FC SD `APM/scripts/` |
| Verify via MAVFTP | `safety.verify_lua_file` | Best-effort file check during `gcs verify-safety` |

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
