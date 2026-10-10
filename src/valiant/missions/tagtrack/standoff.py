"""Task 2 standoff latch (100 m from animal).

Wraps :func:`valiant.comms.competition.deconflict.standoff_reached`. Emits a
crew notification once when the standoff distance is first reached
(idempotent). Does not command the aircraft.
"""

from __future__ import annotations

from typing import Any

from valiant.comms.competition.deconflict import standoff_reached
from valiant.comms.competition.traffic import TASK2_STANDOFF_M
from valiant.comms.gcs_hud import notify_crew

STANDOFF_M = TASK2_STANDOFF_M


class StandoffLatch:
    """Idempotent 100 m standoff detector."""

    def __init__(
        self,
        *,
        min_m: float = STANDOFF_M,
        hud: Any = None,
        say: Any = None,
    ) -> None:
        self.min_m = float(min_m)
        self._hud = hud
        self._say = say
        self._reached = False
        self._announced = False

    @property
    def reached(self) -> bool:
        return self._reached

    def reset(self) -> None:
        self._reached = False
        self._announced = False

    def update(
        self,
        lat: float,
        lon: float,
        animal_lat: float,
        animal_lon: float,
    ) -> bool:
        """Return True once standoff is satisfied (latched thereafter)."""
        if self._reached:
            return True
        if standoff_reached(
            lat,
            lon,
            animal_lat,
            animal_lon,
            min_m=self.min_m,
        ):
            self._reached = True
            self._announce()
            return True
        return False

    def _announce(self) -> None:
        if self._announced:
            return
        self._announced = True
        message = f"Standoff {self.min_m:.0f} m reached"
        if self._say is not None:
            try:
                self._say(message, force=True)
                return
            except TypeError:
                try:
                    self._say(message)
                    return
                except Exception:
                    pass
            except Exception:
                pass
        notify_crew(self._hud, message)
