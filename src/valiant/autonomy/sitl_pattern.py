"""Guided SITL pattern flight: straight legs, turns, then LOITER."""

from __future__ import annotations

import time
from dataclasses import dataclass

from valiant.autonomy.gcs_hud import GcsHudReporter
from valiant.autonomy.guided_motion import GuidedMotionRunner
from valiant.autonomy.orbit_math import wrap_pi
from valiant.autonomy.sitl_preflight import ensure_sitl_guided
from valiant.common.mavlink import (
    MavlinkConnectError,
    connect,
    gcs_statustext_options_from_cfg,
    print_mavlink_connect_error,
    request_guided_telemetry_streams,
)
from valiant.common.sitl_physics import wait_vehicle_pose

_wrap_pi = wrap_pi  # re-export for tests


@dataclass(frozen=True)
class PatternLeg:
    kind: str
    value: float
    label: str


DEFAULT_PATTERN: tuple[PatternLeg, ...] = (
    PatternLeg("forward", 10.0, "Flying forward 10 m"),
    PatternLeg("turn", 90.0, "Turning right 90 deg"),
    PatternLeg("forward", 5.0, "Flying forward 5 m"),
    PatternLeg("turn", -180.0, "Turning left 180 deg"),
    PatternLeg("forward", 5.0, "Flying forward 5 m"),
    PatternLeg("turn", -90.0, "Turning left 90 deg"),
    PatternLeg("forward", 10.0, "Flying forward 10 m"),
)


class SitlPatternRunner:
    """Execute a scripted GUIDED box pattern, then switch to LOITER."""

    def __init__(
        self,
        master,
        cfg: dict,
        *,
        hud: GcsHudReporter | None = None,
        speed_m_s: float = 0.45,
        yaw_rate_rad_s: float = 0.35,
    ):
        self.master = master
        self._motion = GuidedMotionRunner(
            master,
            cfg,
            hud=hud,
            log_tag="Pattern",
            speed_m_s=speed_m_s,
            yaw_rate_rad_s=yaw_rate_rad_s,
            ensure_guided=lambda: ensure_sitl_guided(master, force=True),
        )

    def run(self, legs: tuple[PatternLeg, ...] | None = None) -> None:
        legs = legs or DEFAULT_PATTERN
        self._motion.say("Pattern flight starting")
        request_guided_telemetry_streams(self.master)
        ensure_sitl_guided(self.master, force=True)
        print("[Pattern] Waiting for position telemetry...")
        self._motion.set_last_pose(
            wait_vehicle_pose(
                self.master,
                timeout_s=20.0,
                need_position=True,
                need_attitude=True,
            )
        )
        for leg in legs:
            if leg.kind == "forward":
                self._motion.drive_forward(leg.value, label=leg.label)
            elif leg.kind == "turn":
                self._motion.turn_degrees(leg.value, label=leg.label)
            else:
                raise ValueError(f"Unknown leg kind: {leg.kind}")
        self._motion.set_loiter()
        self._motion.say("Pattern complete - hold in loiter")
        time.sleep(2.0)


def run_pattern_flight(
    *,
    connection: str,
    cfg: dict,
    takeoff_alt_m: float = 5.0,
    skip_preflight: bool = False,
    speed_m_s: float = 0.45,
) -> None:
    """Connect, take off in GUIDED, fly the default box, end in LOITER."""
    from valiant.autonomy.sitl_preflight import arm_guided_takeoff

    baud = int(cfg.get("mavlink", {}).get("baud", 57600))
    try:
        master = connect(connection, baud)
    except MavlinkConnectError as exc:
        print_mavlink_connect_error(exc, prefix="[Pattern]")
        raise SystemExit(1) from None
    gcs_cfg = cfg.get("gcs_monitor", {})
    hud = GcsHudReporter(
        master,
        interval_s=float(gcs_cfg.get("statustext_interval_s", 3.0)),
        options=gcs_statustext_options_from_cfg(cfg, sitl=True),
    )
    try:
        if skip_preflight:
            print("[Pattern] Skipping preflight (assume armed + GUIDED + airborne)")
        else:
            arm_guided_takeoff(
                master,
                takeoff_alt_m=takeoff_alt_m,
                timeout_s=float(cfg.get("sitl", {}).get("preflight_timeout_s", 75.0)),
                ekf_wait_s=float(cfg.get("sitl", {}).get("ekf_wait_s", 45.0)),
            )
            request_guided_telemetry_streams(master)
        runner = SitlPatternRunner(master, cfg, hud=hud, speed_m_s=speed_m_s)
        runner.run()
    finally:
        hud.close()
        try:
            master.close()
        except Exception:
            pass
