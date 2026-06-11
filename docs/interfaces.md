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

Built by `MetricReconstructor` from `CVPacket` + frame geometry + optional VL53L1X MAVLink.

| Field | Source |
|-------|--------|
| `pixel_offset` | Target centre vs frame centre |
| `distance_m` | FOV estimate and/or `DISTANCE_SENSOR` MAVLink |
| `wall_distance_m` | Target distance + wall offset |
| `side_clearance_m` | Lateral margin from frame edge + range |

```python
@dataclass
class MetricPacket:
    target_px: tuple[int, int]
    pixel_offset: tuple[float, float]
    distance_m: float | None
    wall_distance_m: float | None
    side_clearance_m: float | None
    timestamp: float
```

## CV detection methods (`config/vion.yaml`)

| method | Behaviour |
|--------|-----------|
| `hsv` | Purple/blue HSV only - no ONNX required |
| `yolo` | YOLO ONNX for dry; falls back to HSV if model missing |
| `both` | HSV for dry+shot; YOLO supplements dry if HSV finds nothing |

Tune `hsv_dry` / `hsv_shot` / `hsv_min_area_px` for outdoor lighting.

## Bench test

```powershell
python tools\cv_bench_test.py --camera 0
python tools\metric_bench_test.py --camera 0
python tools\metric_bench_test.py --video footage.mp4
```

## Auto-Nav and Spray (`config/vion.yaml`)

- `metric_recon.rangefinder`: `fov_estimate` (default), `vl53l1x`, or `none`
- `metric_recon.min_approach_distance_m`: CONOPS 2m approach validation
- `metric_recon.fire_distance_m`: switch from APPROACHING to AIMING
- `auto_nav.side_clearance_m`: abort if target too close to frame edge
