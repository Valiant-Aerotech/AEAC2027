"""Task 1 wildlife survey mission runner.

Thin orchestration over course/window/cluster/report math and existing
motion helpers. Perception stays label+box+optional text; competition stays
HTTP+penalties. Soft boundary → hold; uncaught faults → hold_after_fault.
Library code must not call SystemExit.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from valiant.comms.gcs_hud import human_state_label, notify_crew
from valiant.core.motion.hold import hold_after_fault
from valiant.core.safety.boundary import BoundaryCheck, BoundaryMonitor
from valiant.missions.survey.cluster import (
    CLUSTER_RADIUS_M,
    ClusterPoint,
    cluster_fixes,
)
from valiant.missions.survey.course import CourseTimer
from valiant.missions.survey.report import ClusterRecord, write_report
from valiant.missions.survey.window import ReportWindow

# Acceptance / gating radii (metres). Clustering radius is CONOPS 5.2.3.7.
WAYPOINT_ARRIVAL_M = 2.0
SEARCH_ENTRY_ACCEPT_M = 5.0
FIX_ACCEPT_M = CLUSTER_RADIUS_M


@dataclass
class SurveyTickStatus:
    """Result of one :meth:`SurveyRunner.tick` call."""

    boundary: BoundaryCheck | None = None
    held: bool = False
    competition_sent: bool = False
    state: str = "SWEEPING"


@dataclass
class SurveyRunner:
    """Owns course clock, report window, and deer-fix list for Task 1."""

    motion: Any = None
    hud: Any = None
    competition: Any = None
    boundary: BoundaryMonitor | None = None
    hold_fn: Callable[[], None] | None = None
    course: CourseTimer = field(default_factory=CourseTimer)
    window: ReportWindow = field(default_factory=ReportWindow)
    fixes: list[ClusterPoint] = field(default_factory=list)
    state: str = "TRANSIT"
    _held: bool = False

    def _announce(self, message: str, *, force: bool = True) -> None:
        motion = self.motion
        if motion is not None and hasattr(motion, "say"):
            motion.say(message, force=force)
            return
        notify_crew(self.hud, message)

    def start_course(self) -> None:
        """Mark takeoff: start course stopwatch and report window."""
        self.course.start()
        if not self.window.started:
            self.window.start()
        self.state = "TRANSIT"
        self._announce(human_state_label(self.state))

    def finish_course(self) -> None:
        """Mark arrival at the search-area boundary."""
        if self.course.started and not self.course.done:
            self.course.finish()
        self.state = "SWEEPING"
        self._announce(human_state_label(self.state))

    def record_fix(
        self,
        lat: float,
        lon: float,
        *,
        tag: str | None = None,
        id: str | None = None,
    ) -> ClusterPoint:
        """Append one ground fix (tag typically from Detection.text)."""
        point = ClusterPoint(lat=float(lat), lon=float(lon), id=id, tag=tag or None)
        self.fixes.append(point)
        return point

    def tick(
        self,
        lat: float,
        lon: float,
        alt_agl: float,
        *,
        armed: bool = False,
        pose_packet: Any = None,
    ) -> SurveyTickStatus:
        """Competition tick + soft-boundary hold check.

        Soft breach calls injectable ``hold_fn`` (or motion hold) once and
        notifies the crew. Returns status for the mission loop.
        """
        competition_sent = False
        if self.competition is not None:
            try:
                if pose_packet is not None:
                    competition_sent = bool(self.competition.tick(pose_packet))
                else:
                    import time

                    from valiant.comms.competition.packet import TelemetryPacket

                    packet = TelemetryPacket(
                        uav_id=getattr(self.competition, "uav_id", "uav"),
                        timestamp=time.time(),
                        lat=float(lat),
                        lon=float(lon),
                        alt_agl_m=float(alt_agl),
                        accuracy_m=1.0,
                        battery_pct=100.0,
                        flight_mode="GUIDED",
                        link_quality=1.0,
                        armed=armed,
                    )
                    competition_sent = bool(self.competition.tick(packet))
            except Exception:
                # Client reconnects internally; never abort the survey loop.
                competition_sent = False

        boundary_check: BoundaryCheck | None = None
        held = False
        if self.boundary is not None:
            boundary_check = self.boundary.update(float(lat), float(lon), float(alt_agl))
            if boundary_check.should_stop and not self._held:
                self._held = True
                held = True
                self.state = "ABORTED"
                self._announce("Soft boundary - holding", force=True)
                self._call_hold()

        return SurveyTickStatus(
            boundary=boundary_check,
            held=held or self._held,
            competition_sent=competition_sent,
            state=self.state,
        )

    def _call_hold(self) -> None:
        if self.hold_fn is not None:
            try:
                self.hold_fn()
            except Exception:
                pass
            return
        motion = self.motion
        if motion is None:
            return
        try:
            hold_after_fault(motion, message="Soft boundary - holding")
        except Exception:
            if hasattr(motion, "hold_position"):
                try:
                    motion.hold_position()
                except Exception:
                    pass

    def build_report_records(self) -> list[ClusterRecord]:
        """Cluster fixes → mean lat/lon + collected tags per cluster."""
        groups = cluster_fixes(self.fixes, radius_m=CLUSTER_RADIUS_M)
        records: list[ClusterRecord] = []
        for i, group in enumerate(groups, start=1):
            lats: list[float] = []
            lons: list[float] = []
            tags: list[str] = []
            for pt in group:
                if isinstance(pt, ClusterPoint):
                    lats.append(pt.lat)
                    lons.append(pt.lon)
                    if pt.tag:
                        tags.append(pt.tag)
                else:
                    lats.append(float(pt[0]))
                    lons.append(float(pt[1]))
            mean_lat = sum(lats) / len(lats)
            mean_lon = sum(lons) / len(lons)
            # Preserve tag order, drop duplicates.
            seen: set[str] = set()
            unique_tags: list[str] = []
            for t in tags:
                if t not in seen:
                    seen.add(t)
                    unique_tags.append(t)
            records.append(
                ClusterRecord(
                    cluster_id=i,
                    count=len(group),
                    lat=mean_lat,
                    lon=mean_lon,
                    tags=tuple(unique_tags),
                )
            )
        return records

    def write_report(self, path: str | Path) -> Path:
        """Write clustered submission report to ``path``."""
        self.state = "REPORTING"
        self._announce(human_state_label(self.state))
        out = write_report(path, self.build_report_records())
        self.state = "COMPLETE"
        self._announce(human_state_label(self.state))
        return out

    def run_two_pass_sweep(
        self,
        motion: Any = None,
        legs: Callable[[], None] | Sequence[Any] | None = None,
    ) -> None:
        """Announce SWEEPING and run injectable pattern / legs callable.

        ``legs`` may be a zero-arg callable (preferred for unit tests) or a
        sequence of callables invoked in order. On exception: hold_after_fault.
        """
        runner_motion = motion if motion is not None else self.motion
        self.state = "SWEEPING"
        self._announce(human_state_label(self.state))
        try:
            if callable(legs):
                legs()
            elif legs is not None:
                for leg in legs:
                    if callable(leg):
                        leg()
            elif runner_motion is not None and hasattr(runner_motion, "run_pattern"):
                runner_motion.run_pattern()
        except Exception as exc:
            message = "Companion fault - holding"
            crew = getattr(exc, "crew_message", None)
            if isinstance(crew, str) and crew:
                message = crew
            self.state = "ABORTED"
            self._announce(message, force=True)
            if runner_motion is not None:
                try:
                    hold_after_fault(runner_motion, message=message)
                except Exception:
                    pass
            # Soft fail: never propagate SystemExit; surface as held state.
            self._held = True
