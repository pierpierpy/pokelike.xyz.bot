"""Heartbeat freshness rules for a running pass."""

from __future__ import annotations

import time
from pathlib import Path

# A live pass touches `<trace>.alive` every few seconds (see llmbench.PassLog).
# Five minutes of silence is the cutoff. Read from the file's mtime so there is
# no wall-clock or timezone guessing.
HEARTBEAT_STALE = 300.0


def _alive_fresh(trace: Path) -> bool:
    """True while the pass that owns this trace is still touching its heartbeat.

    The `.alive` file beside the trace is refreshed by the running process every
    few seconds (see llmbench.PassLog). No file, or an mtime older than
    HEARTBEAT_STALE, means the process is gone.
    """
    try:
        return (time.time() - trace.with_suffix(".alive").stat().st_mtime) < HEARTBEAT_STALE
    except OSError:
        return False
