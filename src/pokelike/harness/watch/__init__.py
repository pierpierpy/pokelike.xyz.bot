"""Watching a pass while it plays: `pokelike model watch`.

This package reads the trace files a pass writes to disk. Nothing here talks to the
running process, so the watch works on a container, on a pass started in another
terminal, and on one that finished last week.

The decision trace (`<model>-passN.jsonl`) is the primary source, with one line per
decision grouped by seed for finished runs. The `.log` supplies whether the pass
ended, and the notebook file supplies notes for harnesses before v4.
"""

# The submodules are kept reachable so that __setattr__ can forward patches.
from . import discover as _discover_mod  # noqa: F401
from . import liveness as _liveness_mod  # noqa: F401
from . import read as _read_mod  # noqa: F401

from .discover import (  # noqa: F401
    BENCH,
    _bench,
    _containers,
    _get_containers,
    _has_container,
    _slug,
    _started,
    _touched,
    folders,
    live,
    newest,
    pick,
)
from .liveness import HEARTBEAT_STALE, _alive_fresh  # noqa: F401
from .read import Pass, Run, read  # noqa: F401
from .dashboard import dashboard, render  # noqa: F401
from .overview import monitor, overview  # noqa: F401


def __setattr__(name: str, value) -> None:
    """Forward attribute patches to the submodule that owns the name.

    Tests monkeypatch names on the package (e.g. `watch.BENCH`), and the functions
    that use those names live in the submodules.
    """
    globals()[name] = value
    if hasattr(_discover_mod, name):
        setattr(_discover_mod, name, value)
    if hasattr(_liveness_mod, name):
        setattr(_liveness_mod, name, value)
    if hasattr(_read_mod, name):
        setattr(_read_mod, name, value)
