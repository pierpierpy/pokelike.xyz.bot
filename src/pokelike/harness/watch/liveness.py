"""Heartbeat freshness rules for a running pass.

In: a trace path. Out: whether the pass that owns it is still alive.
"""

from __future__ import annotations

import time
from pathlib import Path

# Must track llmbench.HEARTBEAT_SECS: a live pass touches `<trace>.alive` every
# few seconds; a stopped one never touches it again. Five minutes of silence is
# the cutoff, generous on purpose so a genuinely slow model is never called dead.
# Read from the file's mtime (the host filesystem's clock, shared by a container's
# bind mount and the host), so there is no wall-clock or timezone guessing.
HEARTBEAT_STALE = 300.0


def _alive_fresh(trace: Path) -> bool:
    """True while the pass that owns this trace is still touching its heartbeat.

    In: a trace path. Out: bool.

    The `.alive` file beside the trace is refreshed by the running process every
    few seconds (see llmbench.PassLog). No file, or an mtime older than
    HEARTBEAT_STALE, means the process is gone: however it went: a clean finish,
    an exception, `kill -9`, an OOM, a removed container, a power cut. This is the
    whole of the liveness test, and it needs nothing to have been written on the
    way out.
    """
    try:
        return (time.time() - trace.with_suffix(".alive").stat().st_mtime) < HEARTBEAT_STALE
    except OSError:
        return False
