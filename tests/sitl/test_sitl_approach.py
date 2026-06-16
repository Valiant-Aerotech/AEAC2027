"""SITL approach tests."""

from __future__ import annotations

import threading
import time

import pytest

from valiant.autonomy.auto_nav.mavlink_driver import MavlinkDriver
from valiant.autonomy.flight.profile import apply_flight_profile
from valiant.autonomy.orchestrator import AutoExtinguisher, STATE_APPROACHING
from valiant.autonomy.packets import MetricPacket
from valiant.common.config import load_config
from valiant.common.synthetic_target_camera import SyntheticTargetCamera

pytestmark = pytest.mark.sitl


def test_synthetic_camera_produces_target():
    cam = SyntheticTargetCamera("tests/fixtures/sitl_approach.json")
    frame = cam.get_frame()
    assert frame is not None
    pkt = cam.get_synthetic_cv_packet()
    assert pkt is not None and pkt.has_dry_target


def test_sitl_velocity_command(sitl_master):
    cfg = apply_flight_profile(load_config("vion"), "sitl")
    nav = MavlinkDriver(sitl_master, cfg)
    metric = MetricPacket(
        target_px=(400, 300),
        pixel_offset=(80.0, 60.0),
        distance_m=2.5,
    )
    nav.move_toward_target(metric, 640, 480, approach_speed=0.2, camera_down=False)
    vx, vy, vz = nav.servo.last_vel_body
    assert abs(vx) + abs(vy) + abs(vz) > 0
    nav.stop()


def test_sitl_orchestrator_reaches_approaching(sitl_master):
    cfg = apply_flight_profile(load_config("vion"), "sitl")
    cfg["camera"]["source"] = "synthetic"
    cfg["camera"]["synthetic_scenario"] = "tests/fixtures/sitl_approach.json"

    ext = AutoExtinguisher(
        cfg,
        connection_string="tcp:127.0.0.1:5760",
        baudrate=57600,
        sitl_mode=True,
        headless=True,
        max_targets=1,
        gcs_ip="127.0.0.1",
    )

    reached = threading.Event()

    def watch():
        deadline = time.time() + 30
        while time.time() < deadline:
            if ext.state == STATE_APPROACHING:
                reached.set()
                break
            time.sleep(0.1)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    loop_thread = threading.Thread(target=ext.loop, daemon=True)
    loop_thread.start()

    assert reached.wait(timeout=25), f"state stuck at {ext.state}"
    ext.request_stop()
    loop_thread.join(timeout=5)
    ext.metric_recon.stop()
    ext.trigger.cleanup()
    ext.gimbal.cleanup()
    ext.camera.cleanup()
