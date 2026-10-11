"""Short fault lines for the ROS log and a later GCS bridge.

``report`` never raises. The same line is published at most once every
5 seconds. Stock PX4 does not subscribe to this text, so QGroundControl
will not show it until a firmware bridge forwards ``~/status_text``.
"""

from __future__ import annotations

import time

try:
    from std_msgs.msg import String
except ImportError:
    String = None

LIMIT_S = 5.0
MAX_CHARS = 50


def clip_status(text: str) -> str:
    line = " ".join(str(text).split())
    if len(line) <= MAX_CHARS:
        return line
    return line[: MAX_CHARS - 3] + "..."


class Status:
    def __init__(self, node) -> None:
        self._node = node
        self._last: dict[str, float] = {}
        self._pub = None
        if String is not None:
            self._pub = node.create_publisher(String, "~/status_text", 10)

    def report(self, text: str) -> None:
        try:
            line = clip_status(text)
            now = time.monotonic()
            previous = self._last.get(line)
            if previous is not None and now - previous < LIMIT_S:
                return
            self._last[line] = now
            self._node.get_logger().warning(line)
            if self._pub is not None and String is not None:
                message = String()
                message.data = line
                self._pub.publish(message)
        except Exception:
            try:
                self._node.get_logger().warning("status report failed")
            except Exception:
                return
