"""Progress display and live fields for a running benchmark."""

from __future__ import annotations

import os
import sys
from typing import Any

from ...shared.tokens import tok as _tok  # noqa: F401 (re-exported for callers)


def progress_bar(**kw: Any) -> Any:
    """Returns a tqdm bar that works both interactively and detached.

    When attached to a terminal, a normal tqdm bar redraws in place. When
    detached (docker compose run -d, a pipe, nohup), each frame becomes a whole
    line with no postfix, ten seconds apart, so `docker logs` works.

    The POKELIKE_PLAIN_BAR env var forces the line-based mode, because
    `docker compose run` allocates a pseudo-tty even with `-d`, making
    `isatty()` unreliable inside a container.
    """
    from tqdm import tqdm

    if sys.stderr.isatty() and not os.environ.get("POKELIKE_PLAIN_BAR"):
        return tqdm(**kw)

    class Lines(tqdm):
        """Line-based tqdm: one line per frame, no postfix."""

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


def live_fields(obs: dict[str, Any], bot: Any = None,
                so_far: tuple[int, int] | None = None) -> dict[str, Any]:
    """Returns progress-bar fields for the current state of a running benchmark.

    Depth is computed from node layers because the engine has no explicit
    map-length field. `so_far` is the cumulative token spend from finished runs,
    so the bar shows both per-run and per-pass totals.
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
        # Between maps or on a non-board screen: show depth without position.
        out["layer"] = f"?/{max(layers)}"

    if bot is not None:
        # Token counts are per-run; on_start resets them.
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
