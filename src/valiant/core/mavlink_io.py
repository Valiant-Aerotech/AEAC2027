"""Thread-safe MAVLink I/O (pymavlink connections are not thread-safe)."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from pymavlink import mavutil


def attach_io_lock(master: mavutil.mavfile) -> mavutil.mavfile:
    if not hasattr(master, "_io_lock"):
        master._io_lock = threading.RLock()  # type: ignore[attr-defined]
    return master


@contextmanager
def mavlink_io(master: mavutil.mavfile) -> Iterator[mavutil.mavfile]:
    lock = getattr(master, "_io_lock", None)
    if lock is None:
        yield master
        return
    with lock:
        yield master
