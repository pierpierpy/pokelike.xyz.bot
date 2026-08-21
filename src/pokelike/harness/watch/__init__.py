"""Watching a pass while it plays: `pokelike model watch`.

WHY THIS READS THE TRACE AND NOTHING ELSE. A pass writes four files and this reads
three of them, all of which are already on disk for other reasons. Nothing here talks
to the running process, so it works the same on a container, on a pass started in
another terminal, and on one that finished last week. It also cannot slow a run down
or, worse, change what the model was asked.

`<model>-passN.jsonl` is the source for everything except two things. One decision per
line, so the last line is where the model is right now, and grouping by seed gives the
finished runs without parsing the columns of the human log. The two exceptions are
whether the pass ended, which is a word in the `.log`, and the notes a harness before
v4 was holding, which only the notebook file records.

WHAT IT DOES NOT DO. No history, no aggregate across passes, no cost. `pokelike model
board` answers those, over recorded results, which is a different question from what is
happening in the next two minutes.
"""

# Keep the submodules reachable so that __setattr__ can forward patches.
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

    Tests monkeypatch names on the package (e.g. `watch.BENCH`, `watch._containers`),
    and the functions that use them live in the submodules. This keeps the test contract
    intact without editing the tests.
    """
    globals()[name] = value
    if hasattr(_discover_mod, name):
        setattr(_discover_mod, name, value)
    if hasattr(_liveness_mod, name):
        setattr(_liveness_mod, name, value)
    if hasattr(_read_mod, name):
        setattr(_read_mod, name, value)
