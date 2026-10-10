"""Task 2 tag-and-track mission runner.

Phases: attach → standoff → track (CSV) → sample → deliver.
Soft boundary → hold; uncaught faults → hold_after_fault. Never SystemExit.
VisualServo is optional and not forked here — GUIDED stays with motion.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from valiant.comms.gcs_hud import human_state_label, notify_crew
from valiant.core.motion.hold import hold_after_fault
from valiant.core.nav.visual_servo import VisualServo  # noqa: F401 — optional; GUIDED stays with motion
from valiant.core.safety.boundary import BoundaryCheck, BoundaryMonitor
from valiant.missions.tagtrack.release import (
    DEFAULT_TRACKER_CHANNEL,
    hold_tracker,
    release_tracker,
)
from valiant.missions.tagtrack.sample import close_gripper, open_gripper
from valiant.missions.tagtrack.standoff import StandoffLatch
from valiant.missions.tagtrack.track_log import append_track_sample

# Approach / standoff gating (metres).
ATTACH_ACCEPT_M = 2.0
STANDOFF_ACCEPT_M = 100.0
SAMPLE_ACCEPT_M = 3.0
DELIVER_ACCEPT_M = 2.0


class TagTrackPhase(str, Enum):
    ATTACH = "ATTACHING"
    STANDOFF = "STANDOFF"
    TRACK = "TRACKING"
    SAMPLE = "COLLECTING"
    DELIVER = "DELIVERING"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


@dataclass
class TagTrackTickStatus:
    phase: TagTrackPhase = TagTrackPhase.ATTACH
    boundary: BoundaryCheck | None = None
    held: bool = False
    standoff_reached: bool = False
    competition_sent: bool = False


@dataclass
class TagTrackRunner:
    """Owns Task 2 phase machine, standoff latch, and track CSV path."""

    motion: Any = None
    hud: Any = None
    competition: Any = None
    boundary: BoundaryMonitor | None = None
    hold_fn: Callable[[], None] | None = None
    visual_servo: Any = None  # VisualServo when provided; unused in dry-run
    master: Any = None
    track_log_path: Path | None = None
    animal_id: str = ""
    animal_lat: float | None = None
    animal_lon: float | None = None
    tracker_channel: int = DEFAULT_TRACKER_CHANNEL
    phase: TagTrackPhase = TagTrackPhase.ATTACH
    standoff: StandoffLatch | None = None
    _held: bool = False
    _samples_logged: int = 0

    def __post_init__(self) -> None:
        if self.standoff is None:
            say = None
            if self.motion is not None and hasattr(self.motion, "say"):
                say = self.motion.say
            self.standoff = StandoffLatch(
                min_m=STANDOFF_ACCEPT_M,
                hud=self.hud,
                say=say,
            )
        if self.track_log_path is not None:
            self.track_log_path = Path(self.track_log_path)

    def _announce(self, message: str, *, force: bool = True) -> None:
        motion = self.motion
        if motion is not None and hasattr(motion, "say"):
            try:
                motion.say(message, force=force)
                return
            except TypeError:
                motion.say(message)
                return
            except Exception:
                pass
        notify_crew(self.hud, message)

    def set_phase(self, phase: TagTrackPhase) -> None:
        self.phase = phase
        self._announce(human_state_label(phase.value))

    def set_animal(self, lat: float, lon: float, *, animal_id: str = "") -> None:
        self.animal_lat = float(lat)
        self.animal_lon = float(lon)
        if animal_id:
            self.animal_id = animal_id

    def attach(self) -> bool:
        """Release tracker onto the animal (servo only; no auto-arm)."""
        self.set_phase(TagTrackPhase.ATTACH)
        ok = release_tracker(self.master, self.tracker_channel)
        if ok:
            self._announce("Tracker released")
        else:
            self._announce("Tracker release skipped (no link)")
        return ok

    def begin_standoff(self) -> None:
        self.standoff.reset()
        self.set_phase(TagTrackPhase.STANDOFF)

    def begin_track(self, path: str | Path | None = None) -> None:
        if path is not None:
            self.track_log_path = Path(path)
        self.set_phase(TagTrackPhase.TRACK)

    def begin_sample(self) -> bool:
        self.set_phase(TagTrackPhase.SAMPLE)
        return open_gripper(self.master, motion=self.motion, hud=self.hud)

    def finish_sample(self) -> bool:
        return close_gripper(self.master, motion=self.motion, hud=self.hud)

    def begin_deliver(self) -> None:
        self.set_phase(TagTrackPhase.DELIVER)

    def complete(self) -> None:
        # Re-latch tracker hold after delivery.
        hold_tracker(self.master, self.tracker_channel)
        self.set_phase(TagTrackPhase.COMPLETE)

    def log_track_point(
        self,
        lat: float,
        lon: float,
        alt_m: float,
        *,
        animal_id: str | None = None,
    ) -> None:
        if self.track_log_path is None:
            return
        append_track_sample(
            self.track_log_path,
            lat=lat,
            lon=lon,
            alt_m=alt_m,
            animal_id=animal_id if animal_id is not None else self.animal_id,
        )
        self._samples_logged += 1

    def tick(
        self,
        lat: float,
        lon: float,
        alt_agl: float,
        *,
        armed: bool = False,
        pose_packet: Any = None,
    ) -> TagTrackTickStatus:
        """Competition + boundary + standoff/track logging for the current phase."""
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
                competition_sent = False

        boundary_check: BoundaryCheck | None = None
        held = False
        if self.boundary is not None:
            boundary_check = self.boundary.update(float(lat), float(lon), float(alt_agl))
            if boundary_check.should_stop and not self._held:
                self._held = True
                held = True
                self.phase = TagTrackPhase.ABORTED
                self._announce("Soft boundary - holding", force=True)
                self._call_hold()

        standoff_ok = False
        latch = self.standoff
        if (
            self.phase is TagTrackPhase.STANDOFF
            and latch is not None
            and self.animal_lat is not None
            and self.animal_lon is not None
        ):
            standoff_ok = latch.update(
                float(lat),
                float(lon),
                self.animal_lat,
                self.animal_lon,
            )
            if standoff_ok and not self._held:
                self.begin_track()

        if self.phase is TagTrackPhase.TRACK and not self._held:
            self.log_track_point(float(lat), float(lon), float(alt_agl))

        # Optional visual-servo tick — runner owns when; does not fork GUIDED.
        if self.visual_servo is not None and hasattr(self.visual_servo, "update"):
            try:
                self.visual_servo.update()
            except Exception:
                pass

        reached = bool(latch.reached) if latch is not None else False
        return TagTrackTickStatus(
            phase=self.phase,
            boundary=boundary_check,
            held=held or self._held,
            standoff_reached=standoff_ok or reached,
            competition_sent=competition_sent,
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

    def run_dry_sequence(
        self,
        *,
        attach_pose: tuple[float, float, float] = (50.1, -110.74, 10.0),
        standoff_pose: tuple[float, float, float] | None = None,
        track_poses: list[tuple[float, float, float]] | None = None,
        animal: tuple[float, float] = (50.1, -110.74),
        animal_id: str = "A1",
    ) -> TagTrackPhase:
        """Offline phase walk for unit tests / CLI --dry-run (no MAVLink)."""
        self.set_animal(animal[0], animal[1], animal_id=animal_id)
        try:
            self.attach()
            self.begin_standoff()
            if standoff_pose is None:
                # ~100 m north of animal.
                from valiant.core.geo import offset_lat_lon

                standoff_pose = (
                    *offset_lat_lon(animal[0], animal[1], 100.0, 0.0),
                    10.0,
                )
            self.tick(*standoff_pose)
            poses = track_poses or [standoff_pose, standoff_pose]
            for pose in poses:
                if self.phase is TagTrackPhase.TRACK:
                    self.tick(*pose)
            self.begin_sample()
            self.finish_sample()
            self.begin_deliver()
            self.tick(*attach_pose)
            self.complete()
        except Exception as exc:
            message = "Companion fault - holding"
            crew = getattr(exc, "crew_message", None)
            if isinstance(crew, str) and crew:
                message = crew
            self.phase = TagTrackPhase.ABORTED
            self._announce(message, force=True)
            if self.motion is not None:
                try:
                    hold_after_fault(self.motion, message=message)
                except Exception:
                    pass
            self._held = True
        return self.phase
