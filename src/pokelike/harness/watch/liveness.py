"""Heartbeat freshness rules for a running pass."""

from __future__ import annotations

import time
from pathlib import Path

from ...shared.heartbeat import HEARTBEAT_STALE  # noqa: F401 (re-exported for readers)


def _alive_fresh(trace: Path) -> bool:
    """True while the pass that owns this trace is still touching its heartbeat.

    The running process refreshes the `.alive` file beside the trace every few
    seconds (see llmbench.PassLog). If the file is missing or its mtime is older
    than HEARTBEAT_STALE, the process is gone.
    """
    try:
        return (time.time() - trace.with_suffix(".alive").stat().st_mtime) < HEARTBEAT_STALE
    except OSError:
        return False
