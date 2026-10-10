"""Sample gripper helpers for Task 2 (thin servo + STATUSTEXT).

Opens/closes a gripper servo channel and announces via ``say`` / notify_crew.
Visual servoing for approach is left to the runner (import VisualServo; do
not fork GUIDED here).
"""

from __future__ import annotations

from typing import Any

from valiant.comms.gcs_hud import notify_crew
from valiant.missions.tagtrack.release import set_tracker_servo

# Gripper PWM defaults (distinct from tracker hold/release channels).
GRIPPER_OPEN_PWM = 1900
GRIPPER_CLOSE_PWM = 1100
DEFAULT_GRIPPER_CHANNEL = 11


def _announce(motion: Any, hud: Any, message: str) -> None:
    if motion is not None and hasattr(motion, "say"):
        try:
            motion.say(message, force=True)
            return
        except TypeError:
            try:
                motion.say(message)
                return
            except Exception:
                pass
        except Exception:
            pass
    notify_crew(hud, message)


def open_gripper(
    master: Any,
    *,
    channel: int = DEFAULT_GRIPPER_CHANNEL,
    pwm: int = GRIPPER_OPEN_PWM,
    motion: Any = None,
    hud: Any = None,
) -> bool:
    """Open the sample gripper and notify the crew."""
    ok = set_tracker_servo(master, channel, pwm)
    _announce(motion, hud, "Gripper open" if ok else "Gripper open failed")
    return ok


def close_gripper(
    master: Any,
    *,
    channel: int = DEFAULT_GRIPPER_CHANNEL,
    pwm: int = GRIPPER_CLOSE_PWM,
    motion: Any = None,
    hud: Any = None,
) -> bool:
    """Close the sample gripper and notify the crew."""
    ok = set_tracker_servo(master, channel, pwm)
    _announce(motion, hud, "Gripper closed" if ok else "Gripper close failed")
    return ok
