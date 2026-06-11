"""Detection and operator target-marking functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Set
import time

from .modes import CameraMode
from .pose import Pose

DEFAULT_ALLOWED_COLOURS: Set[str] = {
    "black", "white", "red", "yellow", "blue", "green"
}


@dataclass
class TargetEvent:
    """One operator-confirmed target sighting."""

    colour: str
    camera_mode: CameraMode
    pose: Pose
    selected_face: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    notes: str = ""


def detect(
    frame,
    detector: Optional[Callable] = None,
    *,
    allowed_colours: Optional[Set[str]] = None,
) -> str:
    """Return target colour from detector callback."""
    allowed = allowed_colours or DEFAULT_ALLOWED_COLOURS
    if detector is None:
        raise NotImplementedError(
            "Plug in the computer-vision detector here. It should return one of: "
            f"{sorted(allowed)}."
        )

    result = detector(frame)
    if isinstance(result, dict):
        colour = result.get("colour")
    else:
        colour = result

    if not isinstance(colour, str):
        raise ValueError(f"detect() expected a colour string, got: {result!r}")

    colour = colour.strip().lower()
    if colour not in allowed:
        raise ValueError(f"Invalid target colour {colour!r}. Allowed: {sorted(allowed)}")

    return colour


def mark_target(
    colour: str,
    camera_mode: int | CameraMode,
    pose: Pose,
    *,
    selected_face: Optional[str] = None,
    notes: str = "",
    allowed_colours: Optional[Set[str]] = None,
) -> TargetEvent:
    """Create a target event after the operator confirms a centred target."""
    allowed = allowed_colours or DEFAULT_ALLOWED_COLOURS
    colour = colour.strip().lower()
    if colour not in allowed:
        raise ValueError(f"Invalid target colour {colour!r}. Allowed: {sorted(allowed)}")

    return TargetEvent(
        colour=colour,
        camera_mode=CameraMode(camera_mode),
        pose=pose,
        selected_face=selected_face,
        timestamp=pose.timestamp,
        notes=notes,
    )
