# Models

ONNX model files are **not committed** to git (see `.gitignore`).

**Default detection uses YOLO** (`config/vion.yaml` `cv.method: yolo`) when `models/dry.pt` or `models/dry.onnx` is present. HSV is still used for blue/wet **shot** confirmation. Set `cv.method: hsv` for purple-only bench without a model file.

## Expected files

| File | Purpose |
|------|---------|
| `dry.onnx` or `dry.pt` | Un-extinguished purple target (trained YOLO) |
| `best.pt` / `best.onnx` | Alternate names (auto-detected) |
| `shot.onnx` | Extinguished blue/wetted (optional; shot also uses HSV) |

## Obtain models

1. **Your trained weights** - copy into `models/`:
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

2. **Copy from old codebase** (interim):
   Copy `old-codebase/integration/pipelines/task_two/models/best.onnx` to `models/dry.onnx` until dry/shot models are trained.

## Config

Model paths are set in `config/vion.yaml` under `cv.models`.
