"""Select a camera backend from config.

Backends are named by import path *as data*, never as a Python import. That
matters for two reasons:

1. The synthetic cameras live in ``valiant.sim``, which sits above perception
   in the layer order. Naming them as strings keeps the dependency out of the
   import graph, so the layering test stays clean. This registry is the one
   whitelisted exception.
2. ``valiant.sim`` pulls in simulation-only machinery. Resolving lazily means
   the Raspberry Pi image can ship without it.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

# source name -> "module.path:ClassName"
BACKENDS: dict[str, str] = {
    "scrcpy": "valiant.perception.camera.base:ScrcpyCamera",
    "webcam": "valiant.perception.camera.base:WebcamCamera",
    "rpi_local": "valiant.perception.camera.rpi:RpiLocalCamera",
    "video": "valiant.perception.camera.replay:VideoReplayCamera",
    "synthetic": "valiant.sim.cameras:SyntheticTimelineCamera",
    "synthetic_world": "valiant.sim.cameras:SyntheticWorldCamera",
}

DEFAULT_SOURCE = "scrcpy"


def resolve_backend(source: str) -> type:
    """Import and return the camera class registered under ``source``."""
    try:
        spec = BACKENDS[source]
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise ValueError(f"Unknown camera source {source!r}; known sources: {known}") from None
    module_path, _, class_name = spec.partition(":")
    try:
        module = import_module(module_path)
    except ImportError as exc:
        raise ImportError(
            f"Camera source {source!r} needs {module_path}, which is not installed: {exc}"
        ) from exc
    return getattr(module, class_name)


def create_camera(cfg: dict, *, phone_ip: str | None = None, video_path: str | None = None) -> Any:
    """Return a started camera matching ``camera.source`` in config."""
    cam_cfg = dict(cfg.get("camera", {}))
    if video_path:
        cam_cfg["video_path"] = video_path
        cam_cfg["source"] = "video"

    source = cam_cfg.get("source", DEFAULT_SOURCE)
    merged = dict(cfg)
    merged["camera"] = cam_cfg

    backend = resolve_backend(source)
    if source == "scrcpy":
        return backend.from_config(merged, phone_ip=phone_ip)

    cam = backend.from_config(merged)
    # Backends that own a capture thread expose start(); replay and synthetic
    # sources are ready on construction.
    if hasattr(cam, "start"):
        cam.start()
    return cam


def camera_depth_mm(camera) -> object | None:
    """Latest depth frame, when the camera provides one."""
    return getattr(camera, "depth_mm", None)


def camera_depth_ok(camera) -> bool:
    return bool(getattr(camera, "depth_ok", False))


def camera_synthetic_detections(camera) -> object | None:
    """Ground-truth DetectionFrame from a synthetic camera, if any.

    Lets SITL runs exercise mission logic without a detection model loaded.
    """
    getter = getattr(camera, "synthetic_detections", None)
    return getter() if callable(getter) else None
