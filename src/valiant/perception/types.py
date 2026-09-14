"""Data contracts passed between perception, navigation and mission code.

These types are deliberately mission-neutral. A detection is a thing found in a
frame; it does not know whether it is a deer, an ear tag, a landing pad or a
leg band. Mission meaning lives in the ``label`` string and in the mission
packages that consume these objects.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Detection:
    """One object located in a single camera frame, in pixel space."""

    cx: int
    cy: int
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    area: int = 0
    confidence: float = 1.0
    label: str = ""
    # Decoded text, when the detector reads characters (e.g. a 2-char ear-tag code).
    text: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return (self.cx, self.cy)


@dataclass
class DetectionFrame:
    """Everything one camera frame produced."""

    detections: list[Detection] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    frame_id: int = 0
    frame_w: int = 0
    frame_h: int = 0
    # Which backend produced this, for debugging mixed pipelines.
    source: str = ""
    debug: dict | None = None

    def __bool__(self) -> bool:
        return bool(self.detections)

    def with_label(self, label: str) -> list[Detection]:
        return [d for d in self.detections if d.label == label]

    def largest(self, label: str | None = None) -> Detection | None:
        """Biggest detection by bbox area, optionally filtered by label."""
        pool = self.detections if label is None else self.with_label(label)
        if not pool:
            return None
        return max(pool, key=lambda d: d.area)


@dataclass(frozen=True)
class RangeFix:
    """Metric reconstruction of one detection, relative to the aircraft.

    Produced by ``perception.metric_recon``; consumed by ``core.nav`` to steer
    and by mission code to decide when a payload action is allowed.
    """

    target_px: tuple[int, int]
    pixel_offset: tuple[float, float]
    # Virtual aim point, when servoing to the true centre would be unsafe.
    aim_px: tuple[int, int] | None = None
    target_offset: tuple[float, float] | None = None

    slant_range_m: float | None = None
    horizontal_range_m: float | None = None
    elevation_deg: float | None = None
    azimuth_deg: float | None = None

    # Best single distance estimate plus the uncertainty band it came from.
    distance_m: float | None = None
    distance_min_m: float | None = None
    distance_max_m: float | None = None
    distance_source: str = ""

    altitude_error_m: float | None = None
    # Metric room between the detection and the nearest frame edge, vertically.
    vertical_margin_m: float | None = None

    timestamp: float = field(default_factory=time.time)

    def range_m(self) -> float | None:
        """Range for approach gating. Horizontal preferred over slant."""
        return self.horizontal_range_m if self.horizontal_range_m is not None else self.distance_m

    @property
    def servo_px(self) -> tuple[int, int]:
        """Pixel the visual servo should drive to centre."""
        return self.aim_px or self.target_px


@dataclass(frozen=True)
class GroundFix:
    """A detection projected onto the ground, in world coordinates.

    This is the unit the Task 1 survey works in: cluster these, count them,
    and report them.
    """

    lat: float
    lon: float
    # Height of the fixed point above the takeoff datum, not of the aircraft.
    alt_agl_m: float = 0.0
    # Rough horizontal uncertainty of the projection, metres.
    accuracy_m: float | None = None
    label: str = ""
    text: str = ""
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
