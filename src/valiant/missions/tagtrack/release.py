"""Tracker hold/release via one MAVLink servo channel.

Uses ``MAV_CMD_DO_SET_SERVO``. Does not arm the vehicle. Never raises
SystemExit — missing master or send faults return False.
"""

from __future__ import annotations

from typing import Any

# Typical open/close PWM for a spring-hold tracker release servo.
HOLD_PWM = 1100
RELEASE_PWM = 1900
DEFAULT_TRACKER_CHANNEL = 10


def set_tracker_servo(
    master: Any,
    channel: int,
    pwm: int,
) -> bool:
    """Command ``channel`` to ``pwm`` via DO_SET_SERVO.

    Returns True on a successful send attempt, False if master is missing or
    the send raises. Does not arm or change flight mode.
    """
    if master is None:
        return False
    try:
        from pymavlink import mavutil

        mav = getattr(master, "mav", None)
        if mav is None:
            return False
        target_system = getattr(master, "target_system", 1)
        target_component = getattr(master, "target_component", 1)
        try:
            from valiant.core.mavlink_io import mavlink_io

            ctx = mavlink_io(master)
        except Exception:
            ctx = None

        def _send() -> None:
            mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,
                int(channel),
                float(pwm),
                0,
                0,
                0,
                0,
                0,
            )

        if ctx is not None:
            with ctx:
                _send()
        else:
            _send()
        return True
    except Exception:
        return False


def hold_tracker(
    master: Any,
    channel: int = DEFAULT_TRACKER_CHANNEL,
    *,
    pwm: int = HOLD_PWM,
) -> bool:
    """Command the tracker servo to the hold (latched) position."""
    return set_tracker_servo(master, channel, pwm)


def release_tracker(
    master: Any,
    channel: int = DEFAULT_TRACKER_CHANNEL,
    *,
    pwm: int = RELEASE_PWM,
) -> bool:
    """Command the tracker servo to the release position."""
    return set_tracker_servo(master, channel, pwm)
