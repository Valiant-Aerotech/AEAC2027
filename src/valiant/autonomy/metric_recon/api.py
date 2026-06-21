"""Public metric recon API (orchestrator, bench, and calibrate tools import from here)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from valiant.autonomy.metric_recon.reconstructor import MetricReconstructor
from valiant.autonomy.metric_recon.geometry_3d import metric_vz_from_altitude_error

if TYPE_CHECKING:
    from pymavlink import mavutil


def create_metric_reconstructor(
    master: mavutil.mavfile | None,
    cfg: dict,
    *,
    sim: bool = False,
) -> MetricReconstructor:
    """Factory for CVPacket -> MetricPacket reconstruction."""
    return MetricReconstructor(master, cfg, sim=sim)


__all__ = [
    "MetricReconstructor",
    "create_metric_reconstructor",
    "metric_vz_from_altitude_error",
]
