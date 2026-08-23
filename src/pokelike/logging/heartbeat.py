"""Heartbeat liveness thread for a running pass.

A running pass touches its `.alive` file every HEARTBEAT_SECS seconds. A watcher
treats any pass whose file has not been touched for HEARTBEAT_STALE seconds as
dead. The signal works because the absence of a fresh touch is what gets detected,
rather than the process promising anything on exit.
"""

from __future__ import annotations

import os
import socket
import threading
from pathlib import Path

from ..shared.heartbeat import HEARTBEAT_STALE  # noqa: F401 (re-exported for callers)

# HEARTBEAT_SECS is the interval in seconds between touches of the .alive file.
HEARTBEAT_SECS = 5.0


class HeartbeatThread:
    """Daemon thread that touches an .alive file until stopped.

    Call `start()` to begin the heartbeat and `stop()` to end it (which also
    removes the file).
    """

    def __init__(self, alive_path: Path) -> None:
        self.alive_path = alive_path
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="pk-heartbeat", daemon=True
        )

    @property
    def owner(self) -> str:
        """Returns a line identifying the process writing this heartbeat."""
        return f"pid={os.getpid()} host={socket.gethostname()}\n"

    def start(self) -> None:
        """Begins the heartbeat loop."""
        self._thread.start()

    def stop(self) -> None:
        """Stops the heartbeat loop and removes the .alive file."""
        self._stop_event.set()
        self._thread.join(timeout=2)
        try:
            self.alive_path.unlink()
        except OSError:
            pass

    def _run(self) -> None:
        """Touches the .alive file in a loop until the stop event is set."""
        while True:
            try:
                self.alive_path.write_text(self.owner, encoding="utf-8")
            except OSError:
                pass
            if self._stop_event.wait(HEARTBEAT_SECS):
                return
