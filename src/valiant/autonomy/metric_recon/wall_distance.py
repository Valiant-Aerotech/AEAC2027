"""Wall and target distance enrichment."""

from __future__ import annotations

from valiant.autonomy.packets import MetricPacket


def enrich_wall_distance(
    packet: MetricPacket,
    cfg: dict,
    *,
    camera_down: bool = True,
) -> MetricPacket:
    """Set wall_distance_m from target distance and camera orientation."""
    metric_cfg = cfg.get("metric_recon", {})
    wall_offset_m = metric_cfg.get("wall_offset_m", 0.0)

    if packet.distance_m is None:
        return packet

    if camera_down:
        # Ground target: wall is behind target along approach axis
        packet.wall_distance_m = packet.distance_m + wall_offset_m
    else:
        # Wall-mounted target: rangefinder points at wall surface
        packet.wall_distance_m = packet.distance_m

    return packet
