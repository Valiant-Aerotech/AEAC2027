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

    @property
    def has_dry_target(self) -> bool:
        return len(self.dry) > 0

    @property
    def primary_dry(self) -> TargetHit | None:
        if not self.dry:
            return None
        return max(self.dry, key=lambda t: t.area)


@dataclass
class MetricPacket:
    """Output of Metric Recon - input to Auto-Nav."""

    target_px: tuple[int, int]
    pixel_offset: tuple[float, float]
    distance_m: float | None = None
    wall_distance_m: float | None = None
    side_clearance_m: float | None = None
    timestamp: float = field(default_factory=time.time)
