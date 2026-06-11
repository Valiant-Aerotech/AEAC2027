# Models

ONNX model files are **not committed** to git (see `.gitignore`).

**Default detection uses HSV** (`config/vion.yaml` `cv.method: hsv`) - no ONNX required for bench or field tests. YOLO models are optional when `cv.method` is `yolo` or `both`.

## Expected files

| File | Purpose |
|------|---------|
| `dry.onnx` | Un-extinguished purple target detection |
| `shot.onnx` | Extinguished blue/wetted target detection |

## Obtain models

1. **Train new models** (Track C8):
   ```powershell
   python -m valiant.autonomy.cv.training.generate_targets
   python -m valiant.autonomy.cv.training.train
   ```

2. **Copy from old codebase** (interim):
   Copy `old-codebase/integration/pipelines/task_two/models/best.onnx` to `models/dry.onnx` until dry/shot models are trained.

## Config

Model paths are set in `config/vion.yaml` under `cv.models`.
