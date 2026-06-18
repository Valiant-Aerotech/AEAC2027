"""Scripted target timelines for SITL — fast closed-loop without physics-linked CV."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valiant.autonomy.packets import CVPacket, TargetHit
from valiant.autonomy.sitl_search import wall_north_m
from valiant.common.config import repo_root
from valiant.common.sitl_physics import (
    VehiclePose,
    body_elevation_deg,
    gimbal_pitch_deg_to_pwm,
    nearest_active_target_ned,
    relative_target_body,
    target_display_color,
)

EXTINGUISHED_BGR = (80, 200, 100)
_DRY_BGR = (180, 50, 180)


class SyntheticTargetCamera:
    """Timeline bbox + optional abstract world; keyframes track mavlink pose when world is set."""

    def __init__(
        self,
        scenario_path: str | Path,
        *,
        width: int = 640,
        height: int = 480,
        synthetic_depth_m: float | None = 3.0,
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
            raw = json.load(f)

        self._world: dict[str, Any] | None = None
        self._missions: list[dict[str, Any]] = []
        self._keyframes: list[dict[str, Any]] = []
        self._mission_index = 0
        self._engaged_target_id: str | None = None

        if isinstance(raw, list):
            self._keyframes = raw
            print(f"[Camera] Synthetic timeline: {path} ({len(raw)} keyframes)")
        else:
            self._world = deepcopy(raw.get("world", {}))
            self._missions = list(raw.get("missions", []))
            if not self._missions:
                raise ValueError("Multi-target scenario needs a non-empty 'missions' list")
            self._load_mission(0)
            n_targets = len(self._world.get("targets", []))
            print(
                f"[Camera] Synthetic sim-world: {path} "
                f"({len(self._missions)} missions, {n_targets} targets)"
            )

        self.width = width
        self.height = height
        self._start = time.time()
        self._last_cv: CVPacket | None = None
        self._last_depth_mm: np.ndarray | None = None
        self._gimbal_pwm_min = gimbal_pwm_min
        self._gimbal_pwm_max = gimbal_pwm_max
        self._gimbal_pwm_neutral = gimbal_pwm_neutral
        self._pose: VehiclePose | None = None
        if synthetic_depth_m is not None and self._last_depth_mm is None:
            mm = int(synthetic_depth_m * 1000)
            self._last_depth_mm = np.full((height, width), mm, dtype=np.uint16)

    @classmethod
    def from_config(cls, cfg: dict) -> SyntheticTargetCamera:
        cam = cfg.get("camera", {})
        gimbal = cfg.get("gimbal", {})
        scenario = cam.get("synthetic_scenario", "tests/fixtures/sitl_approach.json")
        return cls(
            scenario,
            width=int(cam.get("width", 640)),
            height=int(cam.get("height", 480)),
            synthetic_depth_m=cam.get("synthetic_depth_m", 3.0),
            gimbal_pwm_min=int(gimbal.get("pwm_min", 1000)),
            gimbal_pwm_max=int(gimbal.get("pwm_max", 2000)),
            gimbal_pwm_neutral=int(gimbal.get("pwm_neutral", 1500)),
        )

    @property
    def world_scene(self) -> dict[str, Any] | None:
        return self._world

    def set_vehicle_pose(self, pose: VehiclePose) -> None:
        """Link timeline keyframes to mavlink pose when a world scene is loaded."""
        self._pose = pose

    def _wall_range_m(self) -> float | None:
        if self._world is None or self._pose is None or not self._pose.ok:
            return None
        wall_x = wall_north_m(self._world)
        if wall_x is None:
            return None
        return wall_x - self._pose.x

    def _sample_keyframe(self) -> dict | None:
        if not self._keyframes:
            return None
        wall_range = self._wall_range_m()
        if self._world is not None:
            if wall_range is not None:
                return self._sample_keyframe_by_wall_range(wall_range)
            return dict(self._keyframes[0])
        elapsed = time.time() - self._start
        kf = self._keyframes[0]
        for frame in self._keyframes:
            if float(frame.get("t", 0)) <= elapsed:
                kf = frame
            else:
                break
        return kf

    def _sample_keyframe_by_wall_range(self, wall_range: float) -> dict:
        """Map north-axis wall range to authored keyframes (keeps FOV in sync with maps)."""
        kfs = self._keyframes
        wall_x = wall_north_m(self._world) or 5.0
        start_range = wall_x
        end_depth = float(kfs[-1].get("depth_m", 1.1))
        end_range = max(end_depth, 0.8)

        if wall_range >= start_range - 0.05:
            return dict(kfs[0])
        if wall_range <= end_range:
            return dict(kfs[-1])

        frac = (start_range - wall_range) / max(start_range - end_range, 0.1)
        frac = max(0.0, min(1.0, frac))
        t_target = frac * float(kfs[-1].get("t", 10.0))

        prev = kfs[0]
        nxt = kfs[-1]
        for frame in kfs:
            if float(frame.get("t", 0)) <= t_target:
                prev = frame
            else:
                nxt = frame
                break

        t0 = float(prev.get("t", 0))
        t1 = float(nxt.get("t", t0))
        if t1 <= t0:
            return dict(prev)

        alpha = (t_target - t0) / (t1 - t0)
        out: dict[str, Any] = {}
        for key in ("cx", "cy", "bbox_w", "bbox_h", "depth_m"):
            if key in prev and key in nxt:
                v0 = float(prev[key])
                v1 = float(nxt[key])
                out[key] = v0 + alpha * (v1 - v0)
            elif key in prev:
                out[key] = prev[key]
        out["t"] = t_target
        return out

    def _load_mission(self, index: int) -> None:
        if not self._missions:
            return
        self._mission_index = index
        mission = self._missions[index]
        self._keyframes = list(mission.get("keyframes", []))
        self._engaged_target_id = str(mission.get("target_id", ""))
        self._start = time.time()
        if not self._keyframes:
            raise ValueError(f"Mission {index} has no keyframes")

    def mark_extinguished_engaged(self) -> None:
        if not self._engaged_target_id or self._world is None:
            return
        for spec in self._world.get("targets", []):
            if spec.get("id") == self._engaged_target_id:
                spec["extinguished"] = True
                spec["extinguished_color"] = list(EXTINGUISHED_BGR)
                print(f"[Camera] Target {self._engaged_target_id!r} marked extinguished (sim)")
                break

    def advance_to_next_mission(self) -> bool:
        """Start next target timeline after REPOSITION (game-like flow)."""
        if not self._missions:
            return False
        next_idx = self._mission_index + 1
        if next_idx >= len(self._missions):
            self._keyframes = []
            self._engaged_target_id = None
            return False
        self._load_mission(next_idx)
        print(f"[Camera] Advanced to mission {next_idx + 1}/{len(self._missions)}")
        return True

    def gimbal_pwm_hint(self, pose: VehiclePose) -> int | None:
        if self._world is None:
            return self._gimbal_pwm_neutral
        targets = self._world.get("targets", [])
        target = nearest_active_target_ned(pose, targets)
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

    def get_synthetic_cv_packet(self) -> CVPacket | None:
        return self._last_cv

    def _draw_extinguished_markers(self, frame: np.ndarray) -> None:
        if self._world is None:
            return
        for spec in self._world.get("targets", []):
            if not spec.get("extinguished"):
                continue
            pos = spec.get("position_ned")
            if not pos:
                continue
            tx = float(pos[0])
            lane_y = float(self._world.get("approach_lane_y", 0.0))
            ty = float(pos[1])
            scale = 28.0
            cx = int(self.width * 0.5 + (ty - lane_y) * scale * 0.15)
            cy = int(self.height * 0.55 - (tx - 3.5) * scale * 0.12)
            cx = max(20, min(self.width - 20, cx))
            cy = max(20, min(self.height - 20, cy))
            color = target_display_color(spec)
            cv2.circle(frame, (cx, cy), 12, color, -1)

    def get_frame(self) -> np.ndarray | None:
        kf = self._sample_keyframe()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (12, 12, 16)

        if kf is None:
            self._last_cv = CVPacket(dry=[], method="synthetic")
            self._last_depth_mm = None
            self._draw_extinguished_markers(frame)
            label = (
                "ALL TARGETS EXTINGUISHED"
                if self._world and not any(
                    not t.get("extinguished") for t in self._world.get("targets", [])
                )
                else "NO TARGET — repositioning"
            )
            cv2.putText(
                frame, label, (10, self.height - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                EXTINGUISHED_BGR if "ALL" in label else (90, 100, 120),
                1, cv2.LINE_AA,
            )
            return frame

        cx = int(kf.get("cx", self.width // 2))
        cy = int(kf.get("cy", self.height // 2))
        bbox_w = int(kf.get("bbox_w", 80))
        bbox_h = int(kf.get("bbox_h", bbox_w))
        x1 = max(0, cx - bbox_w // 2)
        y1 = max(0, cy - bbox_h // 2)
        x2 = min(self.width, cx + bbox_w // 2)
        y2 = min(self.height, cy + bbox_h // 2)
        area = max((x2 - x1) * (y2 - y1), 1)

        depth_m = kf.get("depth_m")
        if depth_m is not None:
            mm = int(float(depth_m) * 1000)
            self._last_depth_mm = np.full((self.height, self.width), mm, dtype=np.uint16)

        hit = TargetHit(cx=cx, cy=cy, area=area, bbox=(x1, y1, x2, y2), confidence=1.0)
        self._last_cv = CVPacket(dry=[hit], method="synthetic")

        color = _DRY_BGR
        if self._engaged_target_id and self._world:
            for spec in self._world.get("targets", []):
                if spec.get("id") == self._engaged_target_id:
                    color = target_display_color(spec)
                    break

        cv2.circle(frame, (cx, cy), max(bbox_w // 2, 10), color, -1)
        self._draw_extinguished_markers(frame)
        return frame

    @property
    def depth_mm(self) -> np.ndarray | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._last_depth_mm is not None

    def cleanup(self) -> None:
        pass
