"""Progress display and live fields for a running benchmark.

In: observations and bot state mid-run. Out: a dict of progress fields for
a progress bar, or a tqdm bar configured for the environment.
"""

from __future__ import annotations

import os
import sys
from typing import Any


def progress_bar(**kw: Any) -> Any:
    """A tqdm bar that also works when nobody is watching a terminal.

    In: keyword args for tqdm. Out: a tqdm-compatible progress bar.

    Attached to a terminal, the usual thing: a bar that redraws in place several
    times a second, carrying whatever the caller puts in its postfix.

    Detached (docker compose run -d, a pipe, nohup) there is no cursor to
    move. tqdm still writes, but it separates frames with a carriage return and
    never a newline, so the whole run arrives as one enormous line, and Docker's
    log driver holds an unterminated line, so `docker logs` shows NOTHING at all
    until the process exits. Known and old: tqdm#771.

    So without a cursor each frame becomes a whole line, ten seconds apart, and the
    postfix is dropped: it is the live state of one run, which belongs on a bar you
    are watching, not repeated on every line of a file. What the runs actually did
    is already in the log beside the results, one line each. So `docker logs` gets
    a plain bar and nothing else.

    `isatty()` cannot decide this, which is the part that wasted an afternoon:
    `docker compose run` allocates a pseudo-tty EVEN WITH `-d`, so from inside a
    detached container stderr really is /dev/pts/0 and looks interactive while
    nobody is reading it. Hence POKELIKE_PLAIN_BAR, which the image sets: the
    container knows what the process cannot work out for itself.
    """
    from tqdm import tqdm

    if sys.stderr.isatty() and not os.environ.get("POKELIKE_PLAIN_BAR"):
        return tqdm(**kw)

    class Lines(tqdm):
        """One whole line per frame, and no postfix.

        Refusing set_postfix here rather than at the call sites keeps one bar for
        both cases: everything still reports what it always reported, and this
        decides what a log is allowed to be.
        """

        @staticmethod
        def _to_stderr(data: str) -> None:
            data = data.replace("\r", "").strip()
            if data:
                sys.stderr.write(data + "\n")

        def set_postfix(self, *_a: Any, **_k: Any) -> None:
            return

        def set_postfix_str(self, *_a: Any, **_k: Any) -> None:
            return

    class Sink:
        write = staticmethod(Lines._to_stderr)
        flush = staticmethod(sys.stderr.flush)

    return Lines(**{"file": Sink(), "mininterval": 10.0, "ncols": 80, **kw})


def _tok(n: int) -> str:
    """Formats a token count for a progress bar.

    In: the token count. Out: a short string like "35k" or "1.20M".

    The threshold is 999_500 rather than a million because that is where rounding
    to thousands would print `1000k`, which is a million spelled badly.
    """
    return f"{n / 1e6:.2f}M" if n >= 999_500 else f"{n / 1000:.0f}k"


def live_fields(obs: dict[str, Any], bot: Any = None,
                so_far: tuple[int, int] | None = None) -> dict[str, Any]:
    """What is worth seeing WHILE a run is still going, for a progress bar.

    In: the current observation, optionally the bot and cumulative token counts.
    Out: a dict of fields for the bar's postfix.

    Not a log line and not a record: every reading replaces the last one. The
    record is the row written when the run ends.

    Depth comes from the nodes rather than from a field, because the engine has no
    "how long is this map" anywhere: each node carries a `layer`, so the deepest
    one is the boss and `current`'s layer is how far in the bot has got. That
    answers the question a step count cannot: 34 steps means nothing, layer 6 of 7
    means the gym leader is next.

    `so_far` is what the finished runs already spent, so the token fields read
    `this run / the whole pass`. In and out are separate because output costs
    several times more per token, and one total cannot be turned into a bill.

    No seed here on purpose: tqdm renders numbers through its own formatter and
    turns 10000 into `1e+4`, which is worse than useless. The bar's own counter
    already says which run of how many this is.
    """
    run = obs.get("run") or {}
    m = obs.get("map") or {}
    out: dict[str, Any] = {"badges": run.get("badges", 0)}
    if run.get("map") is not None:
        out["map"] = run["map"]

    nodes = m.get("nodes") or []
    layers = [n.get("layer") for n in nodes if isinstance(n.get("layer"), int)]
    here = next((n for n in nodes if n.get("id") == m.get("current")), None)
    if layers and here is not None and isinstance(here.get("layer"), int):
        out["layer"] = f"{here['layer']}/{max(layers)}"
    elif layers:
        # Between maps, or on a screen that is not the board: the depth is still
        # worth showing, the position is simply not known yet.
        out["layer"] = f"?/{max(layers)}"

    if bot is not None:
        # Read off the bot rather than asked for, so nothing else has to know what
        # an LLM is. `on_start` resets these, so they are THIS run's.
        ti = getattr(bot, "tokens_in", 0) or 0
        to = getattr(bot, "tokens_out", 0) or 0
        if ti or to:
            if so_far:
                out["in"] = f"{_tok(ti)}/{_tok(so_far[0] + ti)}"
                out["out"] = f"{_tok(to)}/{_tok(so_far[1] + to)}"
            else:
                out["in"], out["out"] = _tok(ti), _tok(to)
        fell = getattr(bot, "fallbacks", 0) or 0
        if fell:
            out["fell"] = fell
        notes = getattr(bot, "notebook", None)
        if notes is not None:
            out["notes"] = len(notes)
    return out
