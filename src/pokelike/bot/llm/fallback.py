"""Fallback policy and index parsing helpers.

The backup heuristic plays when the model does not answer or returns something
unusable. It prefers what keeps the team alive (heal first if someone is hurt,
otherwise widen the team). The two index helpers convert model output into the
integer the loop needs.
"""

from __future__ import annotations

import re
from typing import Any


def fallback_move_default(state: dict[str, Any]) -> int:
    """Backup choice when the model does not answer or returns an invalid index.

    Prefers heal → catch → item when someone is hurt, otherwise catch → item → heal.
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
    """Coerces a tool argument to int, or returns None. Treats a plain integer
    string like "2" as the integer 2."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().lstrip("+-").isdigit():
        return int(v.strip())
    return None


def _parse_index(text: str, n: int) -> int | None:
    """Last resort: fish a valid index out of a prose answer.

    Returns the last valid number in the text, because a model typically states
    reasoning before its conclusion.
    """
    valid = [v for v in (int(m.group(1)) for m in re.finditer(r"\[?(\d+)\]?", text))
             if 0 <= v < n]
    return valid[-1] if valid else None
