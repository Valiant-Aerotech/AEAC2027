"""Synthetic SITL cameras: world projection and scripted timelines."""

from __future__ import annotations

import math

from valiant.core.kinematics import VehiclePose
from valiant.perception.camera.factory import camera_synthetic_detections, resolve_backend
from valiant.sim.cameras import SyntheticTimelineCamera, SyntheticWorldCamera

WORLD = "tests/fixtures/sitl_survey_world.json"
TIMELINE = "tests/fixtures/sitl_timeline.json"


def _overhead(north_m: float, east_m: float, alt_m: float) -> VehiclePose:
    return VehiclePose(x=north_m, y=east_m, z=-alt_m, ok=True)


def test_world_camera_loads_the_scene():
    cam = SyntheticWorldCamera(WORLD)
    assert len(cam.world_scene["targets"]) == 7


def test_world_camera_sees_nothing_when_pointed_away():
    cam = SyntheticWorldCamera(WORLD)
    # Far south of every decoy, camera forward along +north but they are behind.
    cam.set_vehicle_pose(_overhead(600.0, 0.0, 40.0))
    cam.get_frame()
    frame = cam.synthetic_detections()
    assert frame is not None and not frame.detections


def test_world_camera_detects_targets_ahead():
    cam = SyntheticWorldCamera(WORLD)
    cam.set_vehicle_pose(_overhead(120.0, -40.0, 40.0))
    cam.get_frame()
    frame = cam.synthetic_detections()
    assert frame is not None and frame.detections
    assert all(d.label == "deer" for d in frame.detections)


def test_tag_text_only_appears_once_the_bbox_is_big_enough():
    cam = SyntheticWorldCamera(WORLD)
    # High and far: the decoy subtends few pixels, so the code is illegible.
    cam.set_vehicle_pose(_overhead(60.0, -40.0, 90.0))
    cam.get_frame()
    far = cam.synthetic_detections()
    assert far is not None and all(not d.text for d in far.detections)

    # Close in: at least one code becomes readable.
    cam.set_vehicle_pose(_overhead(175.0, -40.0, 4.0))
    cam.get_frame()
    near = cam.synthetic_detections()
    assert near is not None
    assert any(d.text for d in near.detections)


def test_targets_grow_as_the_aircraft_descends():
    cam = SyntheticWorldCamera(WORLD)
    cam.set_gimbal_pwm(2000)  # look straight down

    def area_overhead_of_d1(alt_m: float) -> int:
        cam.set_vehicle_pose(_overhead(180.0, -40.0, alt_m))
        cam.get_frame()
        return max(d.area for d in cam.synthetic_detections().detections)

    assert area_overhead_of_d1(20.0) > area_overhead_of_d1(90.0)


def test_marking_done_removes_a_target_from_detections():
    cam = SyntheticWorldCamera(WORLD)
    cam.set_vehicle_pose(_overhead(120.0, -40.0, 40.0))
    cam.get_frame()
    before = len(cam.synthetic_detections().detections)
    assert before > 0

    cam.mark_done()
    cam.get_frame()
    assert len(cam.synthetic_detections().detections) == before - 1


def test_world_camera_reports_depth():
    cam = SyntheticWorldCamera(WORLD)
    cam.set_vehicle_pose(_overhead(120.0, -40.0, 40.0))
    cam.get_frame()
    assert cam.depth_ok
    assert math.isfinite(float(cam.depth_mm[0, 0]))


def test_timeline_camera_produces_a_detection():
    cam = SyntheticTimelineCamera(TIMELINE)
    assert cam.get_frame() is not None
    frame = cam.synthetic_detections()
    assert frame is not None and len(frame.detections) == 1
    assert frame.detections[0].label == "deer"


def test_factory_resolves_sim_backends_lazily_by_string():
    # Perception must not statically import sim; the registry holds paths.
    assert resolve_backend("synthetic_world") is SyntheticWorldCamera
    assert resolve_backend("synthetic") is SyntheticTimelineCamera


def test_camera_synthetic_detections_helper():
    cam = SyntheticTimelineCamera(TIMELINE)
    cam.get_frame()
    assert camera_synthetic_detections(cam) is not None
    assert camera_synthetic_detections(object()) is None
