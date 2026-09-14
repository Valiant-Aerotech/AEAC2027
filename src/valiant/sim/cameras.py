"""Synthetic cameras for SITL.

Two backends, both producing a ``DetectionFrame`` alongside the rendered image
so a SITL run can exercise mission logic with no detection model loaded:

``SyntheticWorldCamera``
    World-fixed targets projected through the live SITL pose and gimbal angle.
    This is the one to use for the survey: scatter decoys at NED positions,
    fly over them, and detections appear and disappear for real geometric
    reasons. Because the projection is the inverse of
    ``perception.geometry.project_to_ground``, a SITL run also checks that the
    ground-fix math recovers the positions it was given.

``SyntheticTimelineCamera``
    A scripted sequence of bounding boxes on a clock, independent of pose.
    Cheap and deterministic, for closed-loop tests that should not depend on a
    flying aircraft.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valiant.core.config import repo_root
from valiant.perception.types import Detection, DetectionFrame
from valiant.sim.physics import (
    VehiclePose,
    active_targets,
    body_elevation_deg,
    gimbal_pitch_deg_to_pwm,
    nearest_active_target_ned,
    project_target_ned,
    pwm_to_gimbal_pitch_deg,
    relative_target_body,
    target_display_color,
)

BACKGROUND_BGR = (28, 40, 24)
DONE_BGR = (80, 200, 100)

# Depth frames are uint16 millimetres, matching the Arducam ToF sensor, so
# anything past ~65.5 m saturates. That is not a simulation artefact: the real
# sensor has no useful range at survey altitude either. Saturated means "no
# depth", and metric_recon falls back to the apparent-size estimate.
DEPTH_MAX_MM = 65_535

# Apparent width below which a tag code is not legible. Forces the mission to
# descend or zoom before it can report an ID, which mirrors reality: the codes
# are roughly 3 cm characters.
DEFAULT_TAG_READABLE_PX = 40


def _load_scene(scenario_path: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(scenario_path)
    if not path.is_file():
        path = repo_root() / scenario_path
    if not path.is_file():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")
    with open(path, encoding="utf-8") as f:
        return path, json.load(f)


class SyntheticWorldCamera:
    """World-fixed targets rendered from live SITL position, attitude and gimbal."""

    def __init__(
        self,
        scenario_path: str | Path,
        *,
        width: int = 640,
        height: int = 480,
        hfov_deg: float = 66.0,
        vfov_deg: float = 52.0,
        gimbal_pwm_min: int = 1000,
        gimbal_pwm_max: int = 2000,
        gimbal_pwm_neutral: int = 1500,
        tag_readable_px: int = DEFAULT_TAG_READABLE_PX,
    ):
        path, self._scene = _load_scene(scenario_path)
        self._targets: list[dict[str, Any]] = self._scene.get("targets", [])
        if not self._targets:
            raise ValueError("Scenario needs at least one entry in 'targets'")

        self.width = width
        self.height = height
        self.hfov_deg = float(self._scene.get("hfov_deg", hfov_deg))
        self.vfov_deg = float(self._scene.get("vfov_deg", vfov_deg))
        self.tag_readable_px = int(self._scene.get("tag_readable_px", tag_readable_px))

        self._gimbal_pwm_min = gimbal_pwm_min
        self._gimbal_pwm_max = gimbal_pwm_max
        self._gimbal_pwm_neutral = gimbal_pwm_neutral
        initial_pwm = self._scene.get("initial_gimbal_pwm")
        self._gimbal_pwm = int(initial_pwm) if initial_pwm is not None else gimbal_pwm_neutral

        self._pose = VehiclePose()
        self._frame_id = 0
        self._last_detections: DetectionFrame | None = None
        self._last_depth_mm: np.ndarray | None = None
        self._nearest_target_id: str | None = None
        print(f"[Camera] Synthetic world: {path.name} ({len(self._targets)} targets)")

    @classmethod
    def from_config(cls, cfg: dict) -> SyntheticWorldCamera:
        cam = cfg.get("camera", {})
        gimbal = cfg.get("gimbal", {})
        scenario = cam.get("synthetic_scenario", "tests/fixtures/sitl_survey_world.json")
        return cls(
            scenario,
            width=int(cam.get("width", 640)),
            height=int(cam.get("height", 480)),
            hfov_deg=float(cam.get("hfov_deg", 66.0)),
            vfov_deg=float(cam.get("vfov_deg", 52.0)),
            gimbal_pwm_min=int(gimbal.get("pwm_min", 1000)),
            gimbal_pwm_max=int(gimbal.get("pwm_max", 2000)),
            gimbal_pwm_neutral=int(gimbal.get("pwm_neutral", 1500)),
        )

    # --- inputs from the SITL loop ------------------------------------------

    @property
    def world_scene(self) -> dict[str, Any]:
        return self._scene

    @property
    def vehicle_pose(self) -> VehiclePose:
        return self._pose

    def set_vehicle_pose(self, pose: VehiclePose) -> None:
        self._pose = pose

    def set_gimbal_pwm(self, pwm: int) -> None:
        self._gimbal_pwm = pwm

    def gimbal_pwm_hint(self, pose: VehiclePose) -> int | None:
        """PWM that would point the gimbal at the nearest outstanding target."""
        target = nearest_active_target_ned(pose, self._targets)
        if target is None:
            return self._gimbal_pwm_neutral
        pitch_deg = body_elevation_deg(relative_target_body(pose, target))
        return gimbal_pitch_deg_to_pwm(
            pitch_deg,
            pwm_min=self._gimbal_pwm_min,
            pwm_max=self._gimbal_pwm_max,
            pwm_neutral=self._gimbal_pwm_neutral,
        )

    def mark_done(self, target_id: str | None = None) -> None:
        """Flag a target as handled (tagged, sampled, or already counted)."""
        wanted = target_id or self._nearest_target_id
        if not wanted:
            return
        for spec in self._targets:
            if spec.get("id") == wanted:
                spec["done"] = True
                spec["done_color"] = list(DONE_BGR)
                print(f"[Camera] Target {wanted!r} marked done")
                return

    # --- outputs -------------------------------------------------------------

    def synthetic_detections(self) -> DetectionFrame | None:
        return self._last_detections

    @property
    def depth_mm(self) -> np.ndarray | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._last_depth_mm is not None

    def _project(self, spec: dict, pitch_deg: float):
        pos = spec.get("position_ned")
        if not pos or len(pos) < 3:
            return None
        return project_target_ned(
            (float(pos[0]), float(pos[1]), float(pos[2])),
            self._pose,
            gimbal_pitch_deg=pitch_deg,
            target_diameter_m=float(spec.get("diameter_m", 1.40)),
            frame_w=self.width,
            frame_h=self.height,
            hfov_deg=self.hfov_deg,
            vfov_deg=self.vfov_deg,
        )

    def get_frame(self) -> np.ndarray | None:
        pitch_deg = pwm_to_gimbal_pitch_deg(
            self._gimbal_pwm,
            pwm_min=self._gimbal_pwm_min,
            pwm_max=self._gimbal_pwm_max,
            pwm_neutral=self._gimbal_pwm_neutral,
        )

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = BACKGROUND_BGR
        self._frame_id += 1

        detections: list[Detection] = []
        nearest_depth = float("inf")
        self._nearest_target_id = None

        for spec in self._targets:
            projected = self._project(spec, pitch_deg)
            if projected is None or not projected.visible:
                continue

            cx, cy = projected.cx, projected.cy
            bw, bh = projected.bbox_w, projected.bbox_h
            cv2.circle(frame, (cx, cy), max(bw // 2, 6), target_display_color(spec), -1)

            if spec.get("done"):
                continue

            x1 = max(0, cx - bw // 2)
            y1 = max(0, cy - bh // 2)
            x2 = min(self.width, cx + bw // 2)
            y2 = min(self.height, cy + bh // 2)
            tag = str(spec.get("text", ""))
            legible = bool(tag) and bw >= self.tag_readable_px
            if legible:
                cv2.putText(
                    frame, tag, (x1, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA,
                )
            detections.append(
                Detection(
                    cx=cx,
                    cy=cy,
                    area=max((x2 - x1) * (y2 - y1), 1),
                    bbox=(x1, y1, x2, y2),
                    confidence=1.0,
                    label=str(spec.get("label", "deer")),
                    text=tag if legible else "",
                )
            )
            if projected.depth_m < nearest_depth:
                nearest_depth = projected.depth_m
                self._nearest_target_id = str(spec.get("id", ""))

        self._last_detections = DetectionFrame(
            detections=detections,
            frame_id=self._frame_id,
            frame_w=self.width,
            frame_h=self.height,
            source="synthetic_world",
        )

        if detections:
            mm = min(int(nearest_depth * 1000), DEPTH_MAX_MM)
            self._last_depth_mm = np.full((self.height, self.width), mm, dtype=np.uint16)
        else:
            self._last_depth_mm = None
            remaining = active_targets(self._targets)
            label = "NO TARGET IN VIEW" if remaining else "ALL TARGETS HANDLED"
            cv2.putText(
                frame, label, (10, self.height - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                (90, 100, 120) if remaining else DONE_BGR, 1, cv2.LINE_AA,
            )
        return frame

    def cleanup(self) -> None:
        pass


class SyntheticTimelineCamera:
    """Scripted bounding boxes on a wall-clock timeline, independent of pose."""

    def __init__(
        self,
        scenario_path: str | Path,
        *,
        width: int = 640,
        height: int = 480,
        synthetic_depth_m: float | None = 3.0,
    ):
        path, raw = _load_scene(scenario_path)
        self._keyframes: list[dict[str, Any]] = raw if isinstance(raw, list) else raw.get(
            "keyframes", []
        )
        if not self._keyframes:
            raise ValueError("Timeline scenario needs a non-empty keyframe list")

        self.width = width
        self.height = height
        self._start = time.monotonic()
        self._frame_id = 0
        self._last_detections: DetectionFrame | None = None
        self._last_depth_mm: np.ndarray | None = None
        if synthetic_depth_m is not None:
            mm = min(int(synthetic_depth_m * 1000), DEPTH_MAX_MM)
            self._last_depth_mm = np.full((height, width), mm, dtype=np.uint16)
        print(f"[Camera] Synthetic timeline: {path.name} ({len(self._keyframes)} keyframes)")

    @classmethod
    def from_config(cls, cfg: dict) -> SyntheticTimelineCamera:
        cam = cfg.get("camera", {})
        scenario = cam.get("synthetic_scenario", "tests/fixtures/sitl_timeline.json")
        return cls(
            scenario,
            width=int(cam.get("width", 640)),
            height=int(cam.get("height", 480)),
            synthetic_depth_m=cam.get("synthetic_depth_m", 3.0),
        )

    def reset(self) -> None:
        self._start = time.monotonic()

    def _sample_keyframe(self) -> dict[str, Any]:
        elapsed = time.monotonic() - self._start
        kf = self._keyframes[0]
        for frame in self._keyframes:
            if float(frame.get("t", 0)) <= elapsed:
                kf = frame
            else:
                break
        return kf

    def synthetic_detections(self) -> DetectionFrame | None:
        return self._last_detections

    @property
    def depth_mm(self) -> np.ndarray | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._last_depth_mm is not None

    def get_frame(self) -> np.ndarray | None:
        kf = self._sample_keyframe()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = BACKGROUND_BGR
        self._frame_id += 1

        cx = int(kf.get("cx", self.width // 2))
        cy = int(kf.get("cy", self.height // 2))
        bbox_w = int(kf.get("bbox_w", 80))
        bbox_h = int(kf.get("bbox_h", bbox_w))
        x1 = max(0, cx - bbox_w // 2)
        y1 = max(0, cy - bbox_h // 2)
        x2 = min(self.width, cx + bbox_w // 2)
        y2 = min(self.height, cy + bbox_h // 2)

        depth_m = kf.get("depth_m")
        if depth_m is not None:
            mm = min(int(float(depth_m) * 1000), DEPTH_MAX_MM)
            self._last_depth_mm = np.full((self.height, self.width), mm, dtype=np.uint16)

        self._last_detections = DetectionFrame(
            detections=[
                Detection(
                    cx=cx,
                    cy=cy,
                    area=max((x2 - x1) * (y2 - y1), 1),
                    bbox=(x1, y1, x2, y2),
                    confidence=1.0,
                    label=str(kf.get("label", "deer")),
                    text=str(kf.get("text", "")),
                )
            ],
            frame_id=self._frame_id,
            frame_w=self.width,
            frame_h=self.height,
            source="synthetic_timeline",
        )
        cv2.circle(frame, (cx, cy), max(bbox_w // 2, 10), (60, 90, 170), -1)
        return frame

    def cleanup(self) -> None:
        pass
