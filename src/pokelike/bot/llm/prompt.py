"""Building what the model sees: state rendering, view modes, and tool answers.

Pure functions that turn a game state into text. The hook for changing what the
model looks at is `render_state` on the class; this module holds the default
implementations behind that hook.
"""

from __future__ import annotations

import json
from typing import Any

from pokelike.core import render

from .config import LLMConfigError


def render_state_default(
    state: dict[str, Any],
    state_view: str | list[str] | tuple[str, ...],
    verbose: bool = False,
) -> str:
    """Renders the game state according to the configured view mode.

    In: the state dict, the state_view spec (one of "screen", "json", "both",
    or a list of key names), and a verbose flag. Out: the string the model reads.
    """
    # `state_view` decides what the model is looking at rather than what it is
    # told to do: "screen" is ~880 chars, "json" is ~5900 chars. Six times the
    # tokens is the price of "json", and it is not only money: filling the context
    # with a map the turn does not need takes room from the reasoning it was about
    # to do.
    if isinstance(state_view, str) and state_view == "screen":
        return render.screen(state)
    if isinstance(state_view, str) and state_view in ("json", "both"):
        raw = json.dumps(state, separators=(",", ":"))
        if state_view == "json":
            return raw
        return f"{render.screen(state)}\n\nTHE SAME STATE, IN FULL:\n{raw}"
    if isinstance(state_view, (list, tuple)):
        missing = [k for k in state_view if k not in state]
        if missing:
            # Not an error: a key can be absent on one screen and present on
            # the next: `map` is gone during a battle. Saying so beats a
            # view that quietly shrinks and a run that gets worse for reasons
            # nobody can see.
            if verbose:
                print(f"   [llm] state_view: no {', '.join(missing)} on this screen")
        return json.dumps(
            {k: state[k] for k in state_view if k in state},
            separators=(",", ":"),
        )
    raise LLMConfigError(
        f"state_view is {state_view!r}. Use 'screen', 'json', 'both', a list of "
        f"state keys, or override render_state(state) yourself."
    )


def state_view_label(
    state_view: str | list[str] | tuple[str, ...],
    render_state_overridden: bool,
) -> str:
    """Returns a short label describing the view mode for metadata recording.

    In: the state_view spec and whether `render_state` was overridden by a
    subclass. Out: a string like "screen", "json", "keys:bag,team", or "custom".
    """
    if render_state_overridden:
        return "custom"
    spec = state_view
    return spec if isinstance(spec, str) else "keys:" + ",".join(spec)


def exits_text(state: dict[str, Any]) -> str:
    """Describes where each legal action leads by reading the map edges.

    In: the full state dict. Out: a multi-line string showing each action's index
    and where it leads on the next layer.
    """
    if not state.get("map"):
        return "You are not on the map: this choice opens or closes no paths."
    exits = render.exits_of(state)
    rows = []
    for i, a in enumerate(state["actions"]):
        if i not in exits:
            rows.append(f"  [{i}] {a.get('label', '')[:60]}")
            continue
        follows = ", ".join(exits[i]) if exits[i] else "nothing (end of map)"
        rows.append(f"  [{i}] {a['node']:<12} -> leads to: {follows}")
    return "Exits on the next layer:\n" + "\n".join(rows)
