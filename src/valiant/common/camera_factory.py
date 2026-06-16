"""Camera source selection for GCS scrcpy, onboard Pi, video replay, and synthetic SITL."""

from __future__ import annotations

from valiant.common.camera import ScrcpyCamera


def create_camera(cfg: dict, *, phone_ip: str | None = None, video_path: str | None = None):
    """Return a camera facade matching ``camera.source`` in config."""
    cam_cfg = dict(cfg.get("camera", {}))
    if video_path:
        cam_cfg["video_path"] = video_path
        cam_cfg["source"] = "video"

    source = cam_cfg.get("source", "scrcpy")
    merged = dict(cfg)
    merged["camera"] = cam_cfg

    if source == "rpi_local":
        from valiant.common.rpi_local_camera import RpiLocalCamera

        cam = RpiLocalCamera.from_config(merged)
        cam.start()
        return cam
    if source == "video":
        from valiant.common.video_replay_camera import VideoReplayCamera

        return VideoReplayCamera.from_config(merged)
    if source == "synthetic":
        from valiant.common.synthetic_target_camera import SyntheticTargetCamera

        return SyntheticTargetCamera.from_config(merged)
    return ScrcpyCamera.from_config(merged, phone_ip=phone_ip)


def camera_depth_mm(camera) -> object | None:
    """Return latest depth frame if the camera provides one."""
    if hasattr(camera, "depth_mm"):
        return camera.depth_mm
    return None


def camera_depth_ok(camera) -> bool:
    if hasattr(camera, "depth_ok"):
        return bool(camera.depth_ok)
    return False


def camera_synthetic_cv(camera) -> object | None:
    """Optional pre-built CVPacket (synthetic camera)."""
    if hasattr(camera, "get_synthetic_cv_packet"):
        return camera.get_synthetic_cv_packet()
    return None
