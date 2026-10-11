"""Wildlife-survey submission .txt — write and reparse (round-trip).

Line format (one cluster per line)::

    cluster_id,count,lat,lon[,tag...]

``lat``/``lon`` are the cluster representative (typically the mean of member
fixes). Tags are optional 2-character IDs collected for that cluster. Blank
lines and lines starting with ``#`` are ignored on parse.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Union


@dataclass(frozen=True)
class ClusterRecord:
    """One row in the Task 1 submission report."""

    cluster_id: int
    count: int
    lat: float
    lon: float
    tags: tuple[str, ...] = ()


RecordLike = Union[ClusterRecord, dict]


def _to_record(item: RecordLike, fallback_id: int) -> ClusterRecord:
    if isinstance(item, ClusterRecord):
        return item
    tags = item.get("tags", ())
    if isinstance(tags, str):
        tags_t = (tags,) if tags else ()
    else:
        tags_t = tuple(str(t) for t in tags)
    return ClusterRecord(
        cluster_id=int(item.get("cluster_id", fallback_id)),
        count=int(item["count"]),
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        tags=tags_t,
    )


def _fmt_coord(value: float) -> str:
    """Format a coordinate without trailing zeros; enough digits for field GPS."""
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text if text else "0"


def write_report(path: str | Path, clusters_or_records: Sequence[RecordLike]) -> Path:
    """Write cluster records to ``path`` and return that path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for i, item in enumerate(clusters_or_records, start=1):
        rec = _to_record(item, fallback_id=i)
        parts = [
            str(rec.cluster_id),
            str(rec.count),
            _fmt_coord(rec.lat),
            _fmt_coord(rec.lon),
            *rec.tags,
        ]
        lines.append(",".join(parts))
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def parse_report(path: str | Path) -> list[ClusterRecord]:
    """Parse a file produced by :func:`write_report`."""
    text = Path(path).read_text(encoding="utf-8")
    records: list[ClusterRecord] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            raise ValueError(f"malformed report line (need ≥4 fields): {raw!r}")
        records.append(
            ClusterRecord(
                cluster_id=int(parts[0]),
                count=int(parts[1]),
                lat=float(parts[2]),
                lon=float(parts[3]),
                tags=tuple(parts[4:]),
            )
        )
    return records
