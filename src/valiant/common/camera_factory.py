"""Camera source selection for GCS scrcpy vs onboard Pi."""

from __future__ import annotations

from valiant.common.camera import ScrcpyCamera


def create_camera(cfg: dict, *, phone_ip: str | None = None):
    """Return a camera facade matching ``camera.source`` in config."""
    source = cfg.get("camera", {}).get("source", "scrcpy")
    if source == "rpi_local":
        from valiant.common.rpi_local_camera import RpiLocalCamera

        cam = RpiLocalCamera.from_config(cfg)
        cam.start()
        return cam
    return ScrcpyCamera.from_config(cfg, phone_ip=phone_ip)


def camera_depth_mm(camera) -> object | None:
    """Return latest depth frame if the camera provides one."""
    if hasattr(camera, "depth_mm"):
        return camera.depth_mm
    return None


def camera_depth_ok(camera) -> bool:
    if hasattr(camera, "depth_ok"):
        return bool(camera.depth_ok)
    return False
