"""SITL physics wall approach — requires ArduPilot SITL."""

from __future__ import annotations

import threading
import time

import pytest

from valiant.autonomy.flight.profile import apply_flight_profile
from valiant.autonomy.orchestrator import AutoExtinguisher, STATE_AIMING
from valiant.common.config import load_config

pytestmark = pytest.mark.sitl


def test_sitl_physics_reaches_aiming_within_bounds(sitl_master):
    """Physics wall: AIMING with dry target, no overshoot past x=4.5m."""
    cfg = apply_flight_profile(load_config("vion"), "sitl_physics")

    ext = AutoExtinguisher(
        cfg,
        connection_string="tcp:127.0.0.1:5760",
        baudrate=57600,
        sitl_mode=True,
        headless=True,
        max_targets=1,
        gcs_ip="127.0.0.1",
    )

    dry_frames = 0
    min_dry_before_aiming = 30
    reached = threading.Event()
    pose_at_aiming: list[float] = []
    z_at_aiming: list[float] = []
    target_z_ned = -1.1
    alt_tol = float(cfg.get("sitl", {}).get("alt_align_tolerance_m", 0.25))
    alt_offset = float(cfg.get("sitl", {}).get("alt_offset_m", 0.0))

    def watch():
        nonlocal dry_frames
        deadline = time.time() + 180
        while time.time() < deadline:
            if ext._last_cv is not None and ext._last_cv.has_dry_target:
                dry_frames += 1
            if ext.state == STATE_AIMING:
                if dry_frames >= min_dry_before_aiming:
                    if ext._sitl_pose is not None and ext._sitl_pose.ok:
                        pose_at_aiming.append(ext._sitl_pose.x)
                        z_at_aiming.append(ext._sitl_pose.z)
                    reached.set()
                    break
            time.sleep(0.1)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    loop_thread = threading.Thread(target=ext.loop, daemon=True)
    loop_thread.start()

    assert reached.wait(timeout=170), (
        f"state={ext.state} dry_frames={dry_frames} "
        f"pose={getattr(ext._sitl_pose, 'x', None)}"
    )
    assert pose_at_aiming, "expected pose when AIMING"
    assert pose_at_aiming[0] < 4.5, f"overshoot north: x={pose_at_aiming[0]:.2f}m"
    if ext._sitl_pose is not None and ext._sitl_pose.ok:
        assert abs(ext._sitl_pose.y) < 2.5, f"east drift: y={ext._sitl_pose.y:.2f}m"
    assert z_at_aiming, "expected NED z when AIMING"
    z_err = abs(z_at_aiming[0] - (target_z_ned + alt_offset))
    assert z_err <= alt_tol + 0.15, (
        f"altitude misaligned at AIMING: z={z_at_aiming[0]:.2f} "
        f"target_z={target_z_ned} err={z_err:.2f}m"
    )

    ext.request_stop()
    loop_thread.join(timeout=5)
    ext.metric_recon.stop()
    ext.trigger.cleanup()
    ext.gimbal.cleanup()
    ext.camera.cleanup()
