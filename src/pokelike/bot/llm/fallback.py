"""Fallback policy and index parsing helpers.

The backup heuristic plays when the model does not answer or returns something
unusable. It is not random: it prefers what keeps the team alive (heal first if
someone is hurt, otherwise widen the team).

The two index helpers convert what a model returns into what the loop needs:
_as_index coerces a tool argument, _parse_index fishes a valid index out of prose.
"""

from __future__ import annotations

import re
from typing import Any


def fallback_move_default(state: dict[str, Any]) -> int:
    """Backup choice when the model does not answer or gets it wrong.

    Not random: it prefers what keeps the team alive: heal first if someone
    is hurt, otherwise widen the team. Override it if your bot would rather
    fail differently, but count on it being used: over fifty runs, something
    times out.
    """
    actions = state["actions"]
    team = state.get("team") or []
    hurt = [p for p in team if p["max_hp"] and p["hp"] / p["max_hp"] < 0.4]

    order = ["pokecenter", "catch", "item"] if hurt else ["catch", "item", "pokecenter"]
    for kind in order:
        for i, a in enumerate(actions):
            if a.get("node") == kind:
                return i
    return 0


def _as_index(v: Any) -> int | None:
    """A tool argument as an int, or None. Models often send `"2"` (a string)
    instead of `2`; treat a plain integer string as the integer it obviously
    is, rather than throwing the decision away as malformed."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().lstrip("+-").isdigit():
        return int(v.strip())
    return None


def _parse_index(text: str, n: int) -> int | None:
    """Last resort: fish a valid index out of a prose answer.

    The LAST valid number, not the first: a model states its reasoning before
    its conclusion ("option 0 looks weak, so I'll take 2"), so the answer is
    the last index it names, not the first it mentions.
    """
    valid = [v for v in (int(m.group(1)) for m in re.finditer(r"\[?(\d+)\]?", text))
             if 0 <= v < n]
    return valid[-1] if valid else None
