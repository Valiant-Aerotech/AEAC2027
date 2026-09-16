"""Typed errors for the companion computer.

Library errors live in valiant-mav. Mission-only types stay here.
"""

from __future__ import annotations

from valiant_mav.errors import (
    CREW_MESSAGE_MAX,
    FlightPreconditionError,
    ValiantError,
    clip_crew_message,
)

__all__ = [
    "CREW_MESSAGE_MAX",
    "ConfigError",
    "Degradable",
    "FlightPreconditionError",
    "PerceptionDegraded",
    "ValiantError",
    "clip_crew_message",
]


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
