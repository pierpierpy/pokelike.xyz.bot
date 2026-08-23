"""State rendering and view modes for the LLM harness.

This module provides pure functions that turn a game state into text for the
model.
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
    """Renders the game state according to the configured view mode."""
    # The "screen" view is about 880 chars; "json" is about 5900 chars (six
    # times the tokens).
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
            # A key can be absent on one screen (e.g. `map` during a battle).
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
    """Returns a short label describing the view mode for metadata recording."""
    if render_state_overridden:
        return "custom"
    spec = state_view
    return spec if isinstance(spec, str) else "keys:" + ",".join(spec)


def exits_text(state: dict[str, Any]) -> str:
    """Describes where each legal action leads by reading the map edges."""
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
