# Models

ONNX weights are **not committed** to git (see `.gitignore`). Place trained files here locally.

## Active model (Team)

| File | Purpose |
|------|---------|
| `best.onnx` | Dry (purple) target detection - primary YOLO model |

Default config in `config/vion.yaml`:

```yaml
cv:
  method: yolo
  models:
    dry: models/best.onnx
  yolo_input_size: 320
```

Shot confirmation (blue/wetted target after spray) still uses **HSV** when `cv.method` is `yolo`.

## Optional files

| File | Purpose |
|------|---------|
| `dry.onnx` | Alternate name for dry model (auto-discovered if `best.onnx` missing) |
| `shot.onnx` | Reserved for a future shot-class YOLO model (not wired yet) |

## Test locally

```powershell
python tools\yolo_webcam_test.py --camera 0
python tools\cv_bench_test.py --camera 0
python tools\metric_bench_test.py --camera 0
```

Inference uses **onnxruntime** (no PyTorch required at runtime). Hold a purple target in the **center blue box** (320x320 AI view for `best.onnx`). Detections appear as magenta `dry` boxes.

## Train / export new models

```powershell
python -m valiant.autonomy.cv.training.generate_targets
python -m valiant.autonomy.cv.training.train
# Export: yolo export model=<best.pt> format=onnx
# Copy export to models/best.onnx
```

Training run artifacts go under `models/runs/` (gitignored).
