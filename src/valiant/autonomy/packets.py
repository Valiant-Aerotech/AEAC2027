"""Data packets passed between autonomy modules (see docs/interfaces.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class TargetHit:
    """Single target detection with pixel geometry."""

    cx: int
    cy: int
    area: int = 0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    confidence: float = 1.0

    @property
    def center(self) -> tuple[int, int]:
        return (self.cx, self.cy)


@dataclass
class CVPacket:
    """Output of the CV module - target pixel coordinates by state."""

    dry: list[TargetHit] = field(default_factory=list)
    shot: list[TargetHit] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    frame_id: int = 0
    method: str = ""
    debug: dict | None = None

    @property
    def has_dry_target(self) -> bool:
        return len(self.dry) > 0

    @property
    def primary_dry(self) -> TargetHit | None:
        if not self.dry:
            return None
        return max(self.dry, key=lambda t: t.area)


@dataclass(frozen=True)
class EdgeProximity:
    """Which frame edges the target bbox centre is near."""

    left: bool = False
    right: bool = False
    top: bool = False
    bottom: bool = False

    @property
    def lateral(self) -> bool:
        return self.left or self.right

    @property
    def vertical(self) -> bool:
        return self.top or self.bottom

    @property
    def any_edge(self) -> bool:
        return self.lateral or self.vertical

    def labels(self) -> tuple[str, ...]:
        out: list[str] = []
        if self.left:
            out.append("L")
        if self.right:
            out.append("R")
        if self.top:
            out.append("T")
        if self.bottom:
            out.append("B")
        return tuple(out)


@dataclass
class MetricPacket:
    """Output of Metric Recon - input to Auto-Nav."""

    target_px: tuple[int, int]
    pixel_offset: tuple[float, float]
    aim_px: tuple[int, int] | None = None
    target_offset: tuple[float, float] | None = None
    edge_proximity: EdgeProximity = field(default_factory=EdgeProximity)
    lateral_clearance_ok: bool = True
    vertical_clearance_ok: bool = True
    body_alt_bias_m: float = 0.0
    lateral_clearance_m: float | None = None
    vertical_open_clearance_m: float | None = None
    distance_m: float | None = None
    distance_min_m: float | None = None
    distance_max_m: float | None = None
    distance_source: str = ""
    wall_distance_m: float | None = None
    side_clearance_m: float | None = None
    slant_range_m: float | None = None
    horizontal_range_m: float | None = None
    elevation_deg: float | None = None
    azimuth_deg: float | None = None
    altitude_error_m: float | None = None
    vertical_clearance_m: float | None = None
    timestamp: float = field(default_factory=time.time)

    def planner_range_m(self) -> float | None:
        """Range for fire/approach gating (horizontal preferred)."""
        return self.horizontal_range_m if self.horizontal_range_m is not None else self.distance_m

    @property
    def corner_target(self) -> bool:
        """Legacy: true when target is near left or right image edge."""
        return self.edge_proximity.lateral

    @property
    def edge_lateral(self) -> bool:
        return self.edge_proximity.lateral

    @property
    def edge_vertical(self) -> bool:
        return self.edge_proximity.vertical

    @property
    def body_clearance_ok(self) -> bool:
        return self.lateral_clearance_ok and self.vertical_clearance_ok

    @property
    def servo_px(self) -> tuple[int, int]:
        """Pixel point for visual servo (virtual aim when edge offset active)."""
        return self.aim_px or self.target_px
