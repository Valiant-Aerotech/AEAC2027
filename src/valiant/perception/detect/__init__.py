"""Object detection.

The public surface is deliberately small: a factory that returns something with
a ``detect(frame) -> DetectionFrame`` method. Which backend that is - full-frame
ONNX, tiled inference, or a mission-specific composite - is a config decision.
"""

from valiant.perception.detect.constants import (
    LABEL_DEER,
    LABEL_EAR_TAG,
    LABEL_LANDING_PAD,
    LABEL_LEG_BAND,
    LABEL_SAMPLE,
)
from valiant.perception.detect.exceptions import BadFrameError, CVError, LowConfidenceError
from valiant.perception.detect.subframe_yolo import SubframeYoloDetector, resolve_model_path
from valiant.perception.detect.yolo_onnx import YoloOnnxDetector

__all__ = [
    "BadFrameError",
    "CVError",
    "LABEL_DEER",
    "LABEL_EAR_TAG",
    "LABEL_LANDING_PAD",
    "LABEL_LEG_BAND",
    "LABEL_SAMPLE",
    "LowConfidenceError",
    "SubframeYoloDetector",
    "YoloOnnxDetector",
    "create_detector",
    "resolve_model_path",
]


def create_detector(cfg: dict):
    """Return the detector selected by ``cv.backend`` in config.

    ``subframe`` tiles the frame and runs inference per tile, which is what
    finds small objects in a large image - a deer at 100 m AGL, or a 3 cm ear
    tag. ``full_frame`` is one pass over a centre crop: faster, blinder.
    """
    backend = cfg.get("cv", {}).get("backend", "subframe")
    if backend == "full_frame":
        from pathlib import Path

        path = resolve_model_path(cfg)
        if path is None:
            raise CVError("No detection model found; see cv.models in config")
        conf = float(cfg.get("cv", {}).get("confidence_threshold", 0.35))
        return YoloOnnxDetector(Path(path), conf_thresh=conf)
    return SubframeYoloDetector(cfg)
