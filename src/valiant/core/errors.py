"""Typed errors for the companion computer.

* Library code raises these, never ``SystemExit``.
* Advisory checks (param readback, missing ToF) do not raise at all.
* An in-flight fault holds in GUIDED and tells the crew; it never terminates
  the aircraft. Termination is the flight controller's fence.
* ``crew_message`` is the STATUSTEXT body, already clipped to the 50-char
  MAVLink payload minus the ``VA: `` prefix.
"""

from __future__ import annotations

CREW_MESSAGE_MAX = 46  # 50-char STATUSTEXT minus "VA: "


def clip_crew_message(message: str, *, limit: int = CREW_MESSAGE_MAX) -> str:
    """Fit a message into a Mission Planner STATUSTEXT body."""
    text = " ".join(message.strip().split())
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


class ValiantError(Exception):
    """Something the companion cannot continue with.

    ``detail`` is the full explanation for the terminal and the log.
    ``crew_message`` is what Mission Planner shows.
    """

    def __init__(self, detail: str, *, crew_message: str | None = None):
        super().__init__(detail)
        self.detail = detail
        self.crew_message = clip_crew_message(crew_message or detail)

    def __str__(self) -> str:
        return self.detail


class FlightPreconditionError(ValiantError):
    """GUIDED, arm, takeoff, or pose never arrived. Not yet a flying aircraft."""


class ConfigError(ValiantError):
    """A YAML file is missing or not valid YAML."""


class PerceptionDegraded(ValiantError):
    """A camera, depth sensor, or detector failed.

    Missions should latch this once and poll ``degraded`` on the device rather
    than raising per frame. One bad JPEG must not abort a scored survey.
    """


class Degradable:
    """Mixin: latch a one-shot degradation reason that missions can poll."""

    _degraded: str | None = None

    @property
    def degraded(self) -> str | None:
        return self._degraded

    def latch_degraded(self, reason: str) -> None:
        if self._degraded is None:
            self._degraded = reason
            print(f"[Perception] DEGRADED: {reason}")
