"""Public entry point for metric reconstruction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from valiant.perception.metric_recon.reconstructor import MetricReconstructor

if TYPE_CHECKING:
    from pymavlink import mavutil


def create_metric_reconstructor(
    master: mavutil.mavfile | None,
    cfg: dict,
    *,
    sim: bool = False,
) -> MetricReconstructor:
    return MetricReconstructor(master, cfg, sim=sim)
