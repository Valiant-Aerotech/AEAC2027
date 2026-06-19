# Models

ONNX weights are **not committed** to git (see `.gitignore`). Place trained files here locally.

**Default detection uses YOLO** (`config/rpas.yaml` inherits `cv.method: yolo` from `config/vion.yaml`) when `models/dry.pt`, `models/dry.onnx`, or `models/best.onnx` is present. HSV is still used for blue/wet **shot** confirmation. Set `cv.method: hsv` for purple-only bench without a model file.

## Expected files

| File | Purpose |
|------|---------|
| `best.onnx` | Dry (purple) target detection, primary YOLO model (team default) |
| `dry.onnx` or `dry.pt` | Alternate names (auto-detected) |
| `shot.onnx` | Extinguished blue/wetted (optional; shot also uses HSV) |

Default config in `config/vion.yaml` (inherited by `config/rpas.yaml`):

```yaml
cv:
  method: yolo
  models:
    dry: models/best.onnx    # or models/dry.onnx / models/dry.pt
```

## Setup

1. **Your trained weights**: copy into `models/`:
   ```powershell
   copy path\to\best.pt models\dry.pt
   ```
   Or export ONNX:
   ```powershell
   yolo export model=path\to\best.pt format=onnx imgsz=224
   copy best.onnx models\dry.onnx
   ```

2. **Train in-repo**:
   ```powershell
   python -m valiant.autonomy.cv.training.generate_targets
   python -m valiant.autonomy.cv.training.train
   ```

Shot confirmation uses **HSV** by default. When `models/shot.onnx` is present and `cv.method` is `yolo` or `both`, the detector prefers the shot ONNX model and falls back to HSV.

## Test locally

```powershell
python tools\valiant.py bench cv --camera 0
python tools\valiant.py bench metric --camera 0
```

Inference uses **onnxruntime** (no PyTorch required at runtime). Hold a purple target in the **center blue box**. Detections appear as magenta `dry` boxes.

Training run artifacts go under `models/runs/` (gitignored).
