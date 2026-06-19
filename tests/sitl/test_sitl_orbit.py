"""SITL integration: GUIDED orbit completes at least one lap."""

from __future__ import annotations

import math

import pytest

from valiant.autonomy.field_orbit import FieldOrbitRunner, OrbitPhase
from valiant.autonomy.flight.profile import apply_flight_profile
from valiant.common.config import load_config
from valiant.common.mavlink import request_guided_telemetry_streams
from valiant.common.sitl_physics import drain_vehicle_pose


@pytest.mark.sitl
def test_sitl_orbit_one_lap(sitl_master):
    cfg = apply_flight_profile(load_config("vion"), "sitl_orbit")
    cfg.setdefault("field_orbit", {})["laps"] = 1
    trigger_alt = float(cfg["field_orbit"].get("trigger_alt_m", 10.0))
    cfg["field_orbit"]["orbit_speed_m_s"] = 0.55
    request_guided_telemetry_streams(sitl_master)
    runner = FieldOrbitRunner(
        sitl_master,
        cfg,
        sitl=True,
        skip_standby=True,
    )
    runner.run()
    assert runner.phase in (OrbitPhase.DONE, OrbitPhase.LOITER)
    pose = drain_vehicle_pose(sitl_master)
    assert pose.ok
    assert runner._laps >= 0.95  # noqa: SLF001
    assert -pose.z > trigger_alt * 0.85
    if runner._center is not None:
        cx, cy = runner._center
        dist = math.hypot(pose.x - cx, pose.y - cy)
        assert dist < 1.5
