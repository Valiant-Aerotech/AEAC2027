"""World-fixed targets projected from live ArduPilot SITL pose (gravity/physics in sim)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valiant.autonomy.packets import CVPacket, TargetHit
from valiant.common.config import repo_root
from valiant.common.sitl_physics import (
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

EXTINGUISHED_BGR = (80, 200, 100)


class PhysicsSyntheticCamera:
    """Synthetic CV driven by SITL position, attitude, and gimbal - not a fixed timeline."""

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
    ):
        path = Path(scenario_path)
        if not path.is_file():
            path = repo_root() / scenario_path
        if not path.is_file():
            raise FileNotFoundError(f"Scenario not found: {scenario_path}")
        with open(path, encoding="utf-8") as f:
            self._scene: dict[str, Any] = json.load(f)
        self._targets = self._scene.get("targets", [])
        if not self._targets:
            raise ValueError("Physics scenario needs at least one target in 'targets'")
        self.width = width
        self.height = height
        self.hfov_deg = float(self._scene.get("hfov_deg", hfov_deg))
        self.vfov_deg = float(self._scene.get("vfov_deg", vfov_deg))
        self._gimbal_pwm_min = gimbal_pwm_min
        self._gimbal_pwm_max = gimbal_pwm_max
        self._gimbal_pwm_neutral = gimbal_pwm_neutral
        initial_pwm = self._scene.get("initial_gimbal_pwm")
        self._gimbal_pwm = int(initial_pwm) if initial_pwm is not None else gimbal_pwm_neutral
        self._pose = VehiclePose()
        self._last_cv: CVPacket | None = None
        self._last_depth_mm: np.ndarray | None = None
        self._engaged_target_id: str | None = None
        wall = self._scene.get("wall")
        wall_s = f", wall x={wall.get('x_m')}m" if wall else ""
        print(
            f"[Camera] Physics synthetic: {path} ({len(self._targets)} targets{wall_s})"
        )

    @property
    def world_scene(self) -> dict[str, Any]:
        return self._scene

    @classmethod
    def from_config(cls, cfg: dict) -> PhysicsSyntheticCamera:
        cam = cfg.get("camera", {})
        gimbal = cfg.get("gimbal", {})
        scenario = cam.get("synthetic_scenario", "tests/fixtures/sitl_physics_wall.json")
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

    def set_vehicle_pose(self, pose: VehiclePose) -> None:
        self._pose = pose

    def set_gimbal_pwm(self, pwm: int) -> None:
        self._gimbal_pwm = pwm

    def mark_extinguished_engaged(self) -> None:
        """Turn the engaged target green after a validated kill."""
        if not self._engaged_target_id:
            return
        for spec in self._targets:
            if spec.get("id") == self._engaged_target_id:
                spec["extinguished"] = True
                spec["extinguished_color"] = list(EXTINGUISHED_BGR)
                print(f"[Camera] Target {self._engaged_target_id!r} marked extinguished")
                break
        self._engaged_target_id = None

    def gimbal_pwm_hint(self, pose: VehiclePose) -> int | None:
        """PWM to point gimbal at nearest active world target."""
        target = nearest_active_target_ned(pose, self._targets)
        if target is None:
            return self._gimbal_pwm_neutral
        rel_body = relative_target_body(pose, target)
        pitch_deg = body_elevation_deg(rel_body)
        return gimbal_pitch_deg_to_pwm(
            pitch_deg,
            pwm_min=self._gimbal_pwm_min,
            pwm_max=self._gimbal_pwm_max,
            pwm_neutral=self._gimbal_pwm_neutral,
        )

    @property
    def vehicle_pose(self) -> VehiclePose:
        return self._pose

    def get_synthetic_cv_packet(self) -> CVPacket | None:
        return self._last_cv

    def _draw_wall_guides(self, frame: np.ndarray, pitch_deg: float) -> None:
        wall = self._scene.get("wall")
        if not wall or not self._pose.ok:
            return
        wx = float(wall.get("x_m", 5.0))
        z_top = float(wall.get("z_top", -2.5))
        z_base = float(wall.get("z_base", 0.0))
        for z in (z_top, z_base):
            proj = project_target_ned(
                (wx, 0.0, z),
                self._pose,
                gimbal_pitch_deg=pitch_deg,
                target_diameter_m=0.05,
                frame_w=self.width,
                frame_h=self.height,
                hfov_deg=self.hfov_deg,
                vfov_deg=self.vfov_deg,
                min_depth_m=0.2,
            )
            if proj and 0 <= proj.cx < self.width:
                cv2.circle(frame, (proj.cx, proj.cy), 4, (70, 70, 90), 1)

    def _project_spec(self, spec: dict, pitch_deg: float):
        pos = spec.get("position_ned")
        if not pos or len(pos) < 3:
            return None
        return project_target_ned(
            (float(pos[0]), float(pos[1]), float(pos[2])),
            self._pose,
            gimbal_pitch_deg=pitch_deg,
            target_diameter_m=float(spec.get("diameter_m", 0.20)),
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
        frame[:] = (12, 12, 16)
        depth_plane = np.full((self.height, self.width), 65535, dtype=np.uint16)
        self._draw_wall_guides(frame, pitch_deg)

        visible: list[tuple[dict, object]] = []
        for spec in self._targets:
            projected = self._project_spec(spec, pitch_deg)
            if projected is None or not projected.visible:
                continue
            visible.append((spec, projected))
            color = target_display_color(spec)
            cx, cy = projected.cx, projected.cy
            bw = projected.bbox_w
            cv2.circle(frame, (cx, cy), max(bw // 2, 8), color, -1)

        active_visible = [(s, p) for s, p in visible if not s.get("extinguished")]
        best: tuple[dict, object] | None = None
        for spec, projected in active_visible:
            if best is None or projected.depth_m < best[1].depth_m:
                best = (spec, projected)

        if best is None:
            self._engaged_target_id = None
            self._last_cv = CVPacket(dry=[], method="physics")
            self._last_depth_mm = None
            if not active_targets(self._targets):
                cv2.putText(
                    frame,
                    "ALL TARGETS EXTINGUISHED",
                    (10, self.height - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    EXTINGUISHED_BGR,
                    1,
                    cv2.LINE_AA,
                )
            else:
                cv2.putText(
                    frame,
                    "NO TARGET - repositioning",
                    (10, self.height - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (90, 100, 120),
                    1,
                    cv2.LINE_AA,
                )
            return frame

        spec, projected = best
        self._engaged_target_id = str(spec.get("id", ""))
        cx, cy = projected.cx, projected.cy
        bw, bh = projected.bbox_w, projected.bbox_h
        x1 = max(0, cx - bw // 2)
        y1 = max(0, cy - bh // 2)
        x2 = min(self.width, cx + bw // 2)
        y2 = min(self.height, cy + bh // 2)
        area = max((x2 - x1) * (y2 - y1), 1)
        hit = TargetHit(cx=cx, cy=cy, area=area, bbox=(x1, y1, x2, y2), confidence=1.0)
        self._last_cv = CVPacket(dry=[hit], method="physics")

        mm = int(projected.depth_m * 1000)
        depth_plane[...] = mm
        self._last_depth_mm = depth_plane
        return frame

    @property
    def depth_mm(self) -> np.ndarray | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._last_depth_mm is not None

    def cleanup(self) -> None:
        pass
