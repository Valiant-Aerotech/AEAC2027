"""Holding position, and handing control back to a human pilot.

These are two different things, and conflating them cost us a simulated
aircraft more than once.

ArduCopter's LOITER is a *pilot-controlled* mode. The throttle stick commands
climb rate and centre stick means hold altitude. That is exactly right when a
human is holding a transmitter, and exactly wrong as the terminal state of an
autonomous script: with no RC source, channel 3 reads at or below minimum,
LOITER interprets that as full-down throttle, and the aircraft descends at its
maximum rate until it hits the ground.

That is what happened in SITL. ``tools/sitl/launch_sitl.sh`` runs with
``--no-mavproxy``, so nothing drives the simulated RC channels, and every
scripted flight ended by switching to LOITER. The drop was guaranteed. It is a
simulation artefact in the sense that a live transmitter would have prevented
it, but the underlying rule is real and general:

    An autonomous hold must never depend on a human's stick position.

So the two cases are now separate calls:

``hold_position``
    The default. Stays in GUIDED and streams a zero-velocity setpoint at the
    current position, with a proportional term on altitude. The companion
    stays authoritative, and ``pilot_override`` still correctly detects a real
    pilot grabbing the mode switch.

``hand_back_to_pilot``
    Commands LOITER. Only ever called on hardware, as a deliberate handoff to
    someone holding a transmitter - never as an autonomous terminal state.

``neutralize_sitl_rc`` is belt and braces for the simulator: put channel 3 at
mid-stick and disable simulated RC failsafe, so that even a stray LOITER
behaves.
"""

from __future__ import annotations

import time

RC_MID_PWM = 1500
RC_CHANNEL_THROTTLE = 3
# pymavlink treats 0 as "no change" and 65535 as "release override".
RC_NO_CHANGE = 0

DEFAULT_HOLD_TOLERANCE_M = 0.35


def neutralize_sitl_rc(master, *, throttle_pwm: int = RC_MID_PWM) -> bool:
    """Park simulated RC at a safe neutral. Call once after connecting to SITL.

    Sets channel 3 to mid-stick so a LOITER or ALT_HOLD entered by any path
    reads "hold altitude" rather than "descend", and clears ``SIM_RC_FAIL`` so
    the autopilot does not see an RC failsafe instead.

    Returns False if the link does not support the override, which is the
    normal case on real hardware - never call this in the field.
    """
    try:
        channels = [RC_NO_CHANGE] * 8
        channels[RC_CHANNEL_THROTTLE - 1] = int(throttle_pwm)
        master.mav.rc_channels_override_send(
            master.target_system,
            master.target_component,
            *channels,
        )
        master.mav.param_set_send(
            master.target_system,
            master.target_component,
            b"SIM_RC_FAIL",
            0,
            9,  # MAV_PARAM_TYPE_REAL32
        )
        return True
    except Exception as exc:  # noqa: BLE001 - simulator convenience, never fatal
        print(f"[Hold] Could not neutralize simulated RC: {exc}")
        return False


def release_rc_override(master) -> None:
    """Hand the RC channels back to whatever is really driving them."""
    try:
        master.mav.rc_channels_override_send(
            master.target_system, master.target_component, *([RC_NO_CHANGE] * 8)
        )
    except Exception:  # noqa: BLE001
        pass


def hold_position(
    motion,
    *,
    duration_s: float | None = None,
    tolerance_m: float = DEFAULT_HOLD_TOLERANCE_M,
    tick_s: float = 0.05,
    message: str = "Holding position",
) -> bool:
    """Hold the current position in GUIDED by streaming zero velocity.

    ``motion`` is a :class:`~valiant.core.motion.guided.GuidedMotionRunner`.
    Latches the current altitude on entry and corrects toward it, so the hold
    does not slowly sag.

    Pass ``duration_s=None`` to hold indefinitely - the caller is then
    responsible for breaking out. Returns False if the pilot took over.
    """
    pose = motion.refresh_pose(motion.last_pose)
    hold_alt_m = -pose.z if pose.ok else 0.0
    motion.set_z_hold(-hold_alt_m)
    motion.say(message)

    deadline = None if duration_s is None else time.time() + duration_s
    while deadline is None or time.time() < deadline:
        if motion.check_pilot_override().name != "NONE":
            return False
        motion.start_stream()
        motion.servo.send_velocity_body(
            0.0, 0.0, motion.altitude_vz(hold_alt_m, tolerance_m=tolerance_m)
        )
        motion.set_last_pose(motion.refresh_pose(motion.last_pose))
        time.sleep(tick_s)
    return True


def hand_back_to_pilot(
    motion,
    *,
    message: str = "Loiter - pilot has control",
    timeout_s: float = 8.0,
    allow_without_rc: bool = False,
) -> bool:
    """Switch to LOITER so a human on a transmitter can fly the aircraft home.

    Refuses on a link with no RC input unless ``allow_without_rc`` is set,
    because in that situation LOITER means "descend at maximum rate". Prefer
    :func:`hold_position` for anything autonomous.
    """
    if not allow_without_rc and not _rc_input_present(motion.master):
        motion.say("No RC input - holding in GUIDED instead of LOITER")
        return False

    motion.stop_stream()
    mapping = motion.master.mode_mapping()
    if "LOITER" not in mapping:
        raise RuntimeError(f"LOITER not available on this vehicle: {sorted(mapping)}")

    motion.say(message)
    want = mapping["LOITER"]
    motion.master.set_mode(want)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        motion.heartbeat()
        hb = motion.master.recv_match(type="HEARTBEAT", blocking=True, timeout=1.0)
        if hb is not None and hb.get_srcSystem() == motion.master.target_system:
            if hb.custom_mode == want:
                return True
    print("[Hold] Warning: LOITER not confirmed")
    return False


def _rc_input_present(master, *, timeout_s: float = 1.5, min_pwm: int = 900) -> bool:
    """Whether the autopilot is seeing plausible RC channel values.

    A throttle channel reading zero or below ``min_pwm`` means no transmitter,
    which is precisely the condition that makes LOITER dangerous.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = master.recv_match(type="RC_CHANNELS", blocking=True, timeout=0.5)
        if msg is None:
            continue
        throttle = getattr(msg, f"chan{RC_CHANNEL_THROTTLE}_raw", 0)
        return bool(throttle) and throttle >= min_pwm
    return False
