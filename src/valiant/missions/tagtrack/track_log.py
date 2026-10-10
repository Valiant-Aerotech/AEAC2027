"""Appendix D animal-track CSV writer/reader.

Columns (may tighten later when Appendix D naming is finalized)::

    time_utc,lat,lon,alt_m,animal_id

Round-trip parse mirrors the survey report module: blank lines and ``#``
comments are ignored.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, Union

TRACK_COLUMNS = ("time_utc", "lat", "lon", "alt_m", "animal_id")


@dataclass(frozen=True)
class TrackSample:
    """One Appendix D track row."""

    time_utc: str
    lat: float
    lon: float
    alt_m: float
    animal_id: str = ""


SampleLike = Union[TrackSample, dict]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_sample(item: SampleLike) -> TrackSample:
    if isinstance(item, TrackSample):
        return item
    return TrackSample(
        time_utc=str(item.get("time_utc") or _utc_now_iso()),
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        alt_m=float(item.get("alt_m", item.get("alt", 0.0))),
        animal_id=str(item.get("animal_id", "")),
    )


def write_track_log(path: str | Path, samples: Sequence[SampleLike]) -> Path:
    """Write track samples as CSV and return ``path``."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(TRACK_COLUMNS)
        for item in samples:
            s = _to_sample(item)
            writer.writerow(
                [
                    s.time_utc,
                    f"{s.lat:.8f}".rstrip("0").rstrip(".") or "0",
                    f"{s.lon:.8f}".rstrip("0").rstrip(".") or "0",
                    f"{s.alt_m:.3f}".rstrip("0").rstrip(".") or "0",
                    s.animal_id,
                ]
            )
    return out


def append_track_sample(
    path: str | Path,
    *,
    lat: float,
    lon: float,
    alt_m: float,
    animal_id: str = "",
    time_utc: str | None = None,
) -> Path:
    """Append one sample, creating the file with a header if needed."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out.exists() or out.stat().st_size == 0
    with out.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(TRACK_COLUMNS)
        writer.writerow(
            [
                time_utc or _utc_now_iso(),
                f"{lat:.8f}".rstrip("0").rstrip(".") or "0",
                f"{lon:.8f}".rstrip("0").rstrip(".") or "0",
                f"{alt_m:.3f}".rstrip("0").rstrip(".") or "0",
                animal_id,
            ]
        )
    return out


def parse_track_log(path: str | Path) -> list[TrackSample]:
    """Parse a file produced by :func:`write_track_log` / :func:`append_track_sample`."""
    text = Path(path).read_text(encoding="utf-8")
    samples: list[TrackSample] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Skip header row.
        if line.lower().startswith("time_utc"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            raise ValueError(f"malformed track line (need ≥4 fields): {raw!r}")
        animal_id = parts[4] if len(parts) > 4 else ""
        samples.append(
            TrackSample(
                time_utc=parts[0],
                lat=float(parts[1]),
                lon=float(parts[2]),
                alt_m=float(parts[3]),
                animal_id=animal_id,
            )
        )
    return samples
