"""Heartbeat freshness rules for a running pass."""

from __future__ import annotations

import time
from pathlib import Path

from ...shared.heartbeat import HEARTBEAT_STALE  # noqa: F401 (re-exported for readers)


def heartbeat(folder: Path) -> Path | None:
    """Returns the heartbeat file of the pass in this folder, or None when there is none.

    A pass removes its `.alive` file when it ends, so a folder holds one while a
    pass is playing and none afterwards. The file is found by looking for it
    rather than by deriving its name from another file, because deriving the name
    tied liveness to which file was taken as the trace: a companion file taken as
    the trace named a heartbeat that nothing writes, and a pass playing right now
    read as dead.
    """
    beats = sorted(folder.glob("*.alive"), key=lambda f: f.stat().st_mtime)
    return beats[-1] if beats else None


def _alive_fresh(folder: Path) -> bool:
    """True while the pass in this folder is still touching its heartbeat.

    The running process refreshes its `.alive` file every few seconds (see
    llmbench.PassLog). A missing file means the pass removed it on the way out.
    An mtime older than HEARTBEAT_STALE means the process died without the chance
    to remove it, which is what a kill -9 or a lost container leaves behind.
    """
    beat = heartbeat(folder)
    if beat is None:
        return False
    try:
        return (time.time() - beat.stat().st_mtime) < HEARTBEAT_STALE
    except OSError:
        return False
