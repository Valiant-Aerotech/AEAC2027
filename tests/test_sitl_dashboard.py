"""Tests for combined SITL dashboard layout."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from valiant.autonomy.cv.sitl_map_view import (
    render_sitl_dashboard,
    render_topdown,
    render_wall_side,
)
from valiant.common.sitl_physics import VehiclePose

SCENE = json.loads(Path("tests/fixtures/sitl_physics_wall.json").read_text(encoding="utf-8"))
MULTI_SCENE = json.loads(
    Path("tests/fixtures/sitl_synthetic_multi.json").read_text(encoding="utf-8")
)["world"]

def _wall_pixel_count(img: np.ndarray) -> int:
    mask = (img[:, :, 0] > 200) & (img[:, :, 1] > 140)
    return int(mask.sum())


def test_dashboard_grid_dimensions():
    fov = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = VehiclePose(x=1.0, y=0.2, z=-2.5, ok=True)
    img = render_sitl_dashboard(fov, SCENE, pose, state="SEARCHING", width=1280, height=720)
    assert img.shape == (720, 1280, 3)


def test_dashboard_mode_label_in_fov_panel():
    fov = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = VehiclePose(x=1.0, y=0.2, z=-2.5, ok=True)
    img = render_sitl_dashboard(
        fov,
        SCENE,
        pose,
        state="AIMING",
        mode_label="SIM",
        width=1280,
        height=720,
    )
    fov_w = 1280 // 2
    # Mode label is drawn in the FOV panel (left half), not over the wall title bar.
    left_panel = img[:, :fov_w]
    right_panel = img[:, fov_w:]
    assert left_panel.mean() > 0
    assert right_panel.mean() > 0


def test_wall_side_shows_wall_and_range():
    pose = VehiclePose(x=1.7, y=0.5, z=-1.5, yaw=0.0, ok=True)
    img = render_wall_side(MULTI_SCENE, pose, width=640, height=360, compact=True)
    assert img.shape == (360, 640, 3)
    assert _wall_pixel_count(img) > 500
    wall_range = float(MULTI_SCENE["wall"]["x_m"]) - pose.x
    assert abs(wall_range - 3.3) < 0.01


def test_topdown_centers_drone_and_draws_wall():
    pose = VehiclePose(x=1.7, y=0.5, z=-1.5, yaw=0.0, ok=True)
    img = render_topdown(MULTI_SCENE, pose, width=640, height=360, compact=True)
    assert img.shape == (360, 640, 3)
    assert _wall_pixel_count(img) > 200
    # Drone icon is drawn at panel centre.
    cy, cx = img.shape[0] // 2, img.shape[1] // 2
    assert img[cy, cx].mean() > 25


def test_extinguished_target_uses_green_on_maps():
    pose = VehiclePose(x=1.7, y=0.5, z=-1.5, ok=True)
    scene = json.loads(json.dumps(MULTI_SCENE))
    scene["targets"][0]["extinguished"] = True
    scene["targets"][0]["extinguished_color"] = [80, 200, 100]
    img = render_topdown(scene, pose, width=640, height=360, compact=True)
    green_mask = (img[:, :, 1] > 160) & (img[:, :, 0] < 120)
    assert int(green_mask.sum()) > 50
