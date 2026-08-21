"""Action list and move tutor rendering.

Pure functions that turn the legal choices into printable text.
"""

from __future__ import annotations

from typing import Any


def actions_view(actions: list[dict]) -> str:
    """Formats the numbered action list for a turn.

    In: the `actions` list from a state. Out: the printable block, one per option.

    The `tooltip` is the text the game puts on screen when the pointer rests on
    that node: the trainer's archetype and which types they use, a gym leader's
    roster with levels, what a trade does. Someone playing in a browser reads it
    before choosing, so a terminal that left it out was the poorer view, not the
    equal one.

    Absent on anything that is not a map node, and absent on older recordings,
    hence the `.get`.
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

    In: the full observation dict. Out: comparison table (empty if no offers).

    The buttons read "-> SURF:Wartortle Lv35" and carry neither power nor type,
    so the comparison that decides the choice is not on screen at all. It is in
    the state (`team[i].move` and `offered_moves[i]`) and this is where it
    becomes readable.

    Renders whenever `offered_moves` is present, which is every turn: the bridge
    asks the engine what the tutor WOULD offer each member unconditionally, so
    the question can be answered before reaching a tutor. Gating on the screen is
    therefore the caller's job, and `screen()` does it. Kept that way round on
    purpose, since a bot that wants to plan several maps ahead has a reason to
    call this off a tutor screen and no way to get it back if this function
    refused.
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
