"""Heartbeat liveness thread for a running pass.

A running pass touches its `.alive` file every HEARTBEAT_SECS; `model watch`
treats a pass whose file has not been touched for HEARTBEAT_STALE seconds as no
longer running. This is the ONE liveness signal that survives EVERY way a pass
can stop: a clean return, an exception, `kill -9`, an OOM, the container being
removed, the machine losing power: because all of them stop the touches. We
read the ABSENCE of a fresh heartbeat, never a promise the pass made about
itself on the way out, which a crash would skip.
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
        # So `model stop <stamp>` can signal exactly this pass rather than guessing
        # from a model name. The pid is only meaningful on the machine that wrote
        # it; inside a container it belongs to that container's namespace, which is
        # why the hostname goes with it: Docker sets it to the container id, so the
        # host can turn one into `docker stop`. Liveness still reads only the
        # mtime, so the content costs nothing.
        return f"pid={os.getpid()} host={socket.gethostname()}\n"

    def start(self) -> None:
        """Begins the heartbeat loop."""
        self._thread.start()

    def stop(self) -> None:
        """Stops the heartbeat and removes the .alive file.

        In: nothing. Out: the .alive file is unlinked if possible.
        """
        # Stop the heartbeat and take its file with it: a clean close means the
        # pass is over NOW, so `model watch` should not wait for the mtime to age
        # out. Join first so the thread cannot touch the file back into existence
        # after we unlink it (Event.wait returns the instant it is set, so this is
        # immediate). A crash never reaches here, and does not need to, because
        # the thread dies with the process and the file simply stops being touched.
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
                # Rewritten rather than touched, so the owner line is restored if
                # anything removed the file, and the mtime moves either way. A
                # reader that catches it mid-write sees a short or empty file and
                # falls back to matching the pass by model, which is why the
                # stopper never trusts this content blindly.
                self.alive_path.write_text(self.owner, encoding="utf-8")
            except OSError:
                pass
            if self._stop_event.wait(HEARTBEAT_SECS):
                return
