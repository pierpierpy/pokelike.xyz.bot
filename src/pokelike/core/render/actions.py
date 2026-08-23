"""Action list and move tutor rendering.

Pure functions that turn the legal choices into printable text.
"""

from __future__ import annotations

from typing import Any


def actions_view(actions: list[dict]) -> str:
    """Formats the numbered action list for a turn.

    This function takes the `actions` list from a state and returns the
    printable block with one line per option.

    The `tooltip` field carries the hover text the game shows for a map node
    (trainer archetype, gym roster, trade details). It is absent on non-node
    actions and on older recordings, hence the `.get`.
    """
    if not actions:
        return "  (no actions)"
    rows = []
    for i, a in enumerate(actions):
        if a["kind"] == "node":
            tip = f"  {a['tooltip']}" if a.get("tooltip") else ""
            rows.append(f"  [{i}] go to node {a['id']:<6} ({a['node']}){tip}")
        else:
            rows.append(f"  [{i}] {a['label']}")
    return "\n".join(rows)


def tutor_view(obs: dict[str, Any]) -> str:
    """Renders the move tutor offer against what each Pokemon already has.

    This function takes the full observation dict and returns a comparison table
    (empty string if no offers are available).

    The tutor buttons carry only species and level, not power or type, so this
    function builds the comparison from `team[i].move` and `offered_moves[i]`.

    The `offered_moves` field is present every turn (the bridge asks the engine
    unconditionally), so gating on the tutor screen is the caller's job.
    """
    offered = obs.get("offered_moves") or {}
    team = obs.get("team") or []
    if not offered or not team:
        return ""
    rows = []
    for i, p in enumerate(team):
        new = offered.get(str(i)) or offered.get(i) or {}
        if not new.get("name"):
            continue
        cur = p.get("move") or {}
        gain = (new.get("power") or 0) - (cur.get("power") or 0)
        arrow = "+" if gain > 0 else ("=" if gain == 0 else "")
        rows.append(
            f"  {i}. {p['name']:<13}{cur.get('name', '?'):<15}{cur.get('power', '?'):>4}"
            f"   ->  {new['name']:<15}{new.get('power', '?'):>4}  {arrow}{gain if gain else ''}"
        )
    return "\n".join(rows)
