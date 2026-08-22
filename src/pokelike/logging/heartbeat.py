"""Heartbeat liveness thread for a running pass.

A running pass touches its `.alive` file every HEARTBEAT_SECS; a watcher treats
a pass whose file has not been touched for HEARTBEAT_STALE seconds as no longer
running. This is the ONE liveness signal that survives EVERY way a pass can stop:
a clean return, an exception, `kill -9`, an OOM, the container being removed, the
machine losing power: because all of them stop the touches. We read the ABSENCE
of a fresh heartbeat, never a promise the pass made about itself on the way out,
which a crash would skip.
"""

from __future__ import annotations

import os
import socket
import threading
from pathlib import Path

# Seconds between touches of the .alive file.
HEARTBEAT_SECS = 5.0

# Seconds after which a pass whose .alive has not been touched is considered dead.
HEARTBEAT_STALE = 300.0


class HeartbeatThread:
    """Daemon thread that touches an .alive file until stopped.

    In: the path to the .alive file. Out: call start() to begin, stop() to end.
    """

    def __init__(self, alive_path: Path) -> None:
        self.alive_path = alive_path
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="pk-heartbeat", daemon=True
        )

    @property
    def owner(self) -> str:
        """Who is playing this pass, written into the heartbeat file.

        In: nothing. Out: a line like `pid=1234 host=7dae1e302082`.
        """
        return f"pid={os.getpid()} host={socket.gethostname()}\n"

    def start(self) -> None:
        """Begins the heartbeat loop."""
        self._thread.start()

    def stop(self) -> None:
        """Stops the heartbeat and removes the .alive file.

        In: nothing. Out: the .alive file is unlinked if possible.
        """
        self._stop_event.set()
        self._thread.join(timeout=2)
        try:
            self.alive_path.unlink()
        except OSError:
            pass

    def _run(self) -> None:
        """Touch the .alive file until the pass ends, by whatever means."""
        while True:
            try:
                self.alive_path.write_text(self.owner, encoding="utf-8")
            except OSError:
                pass
            if self._stop_event.wait(HEARTBEAT_SECS):
                return
