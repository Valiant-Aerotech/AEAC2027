"""AEAC competition telemetry server client and airspace deconfliction."""

from valiant.comms.competition.client import (
    CompetitionClient,
    HttpTransport,
    LoopbackTransport,
    make_client,
)
from valiant.comms.competition.deconflict import DeconflictAdvice, advise, standoff_reached
from valiant.comms.competition.packet import REQUIRED_FIELDS, TelemetryPacket
from valiant.comms.competition.penalties import OCCURRENCE_CAP, PenaltyBook, PenaltyType
from valiant.comms.competition.traffic import DEFAULT_KEEPOUT_RADIUS_M, TrafficAircraft

__all__ = [
    "DEFAULT_KEEPOUT_RADIUS_M",
    "OCCURRENCE_CAP",
    "REQUIRED_FIELDS",
    "CompetitionClient",
    "DeconflictAdvice",
    "HttpTransport",
    "HttpTransport",
    "LoopbackTransport",
    "PenaltyBook",
    "PenaltyType",
    "TelemetryPacket",
    "TrafficAircraft",
    "advise",
    "make_client",
    "standoff_reached",
]
