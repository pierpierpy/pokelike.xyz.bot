"""Text rendering of the game state, frozen beside the harness that uses it.

This is a copy of pokelike.core.render, not an import, because the shared module
evolves freely for the CLI and bot submissions while a benchmark needs the renderer
to stay fixed. Once a result exists beside this file, editing the file would change
what every recorded score on this harness meant.

Two differences from the v0/v2 copy:

1. actions_view() prints each node's tooltip (trainer archetype, types, gym
   rosters, trade descriptions), read from the engine's getNodeLabel function.
2. screen() shows the move tutor block only on the tutor screen, not every turn.

Only screen() and team_view() are called by the harness. The shared module's
graph_view, score_view, trace_view, and ending_view are not included here because
the harness never calls them.

Everything is rebuilt from the state dict (a JavaScript object read as JSON). No
pixels are inspected.
"""

from __future__ import annotations

from typing import Any

ICONS = {
    "start": "@", "battle": "x", "trainer": "T", "catch": "o", "item": "i",
    "pokecenter": "+", "question": "?", "trade": "$", "move_tutor": "M",
    "boss": "B", "shiny": "*", "pokemart": "S", "mutation": "%",
    "evil_team": "E", "silver": "s", "legendary": "L",
}

LEGEND = (
    "@ start    x wild fight   T trainer   o catch    i item     + pokecenter\n"
    "? unknown  $ trade        M tutor      B boss   S shop     * shiny"
)


def map_view(m: dict[str, Any] | None) -> str:
    if not m:
        return "  (no map)"
    by_layer: dict[int, list[dict]] = {}
    for n in m["nodes"]:
        if not n["revealed"]:
            continue
        by_layer.setdefault(n["layer"], []).append(n)

    rows = []
    for layer in sorted(by_layer):
        cells = []
        for n in sorted(by_layer[layer], key=lambda x: x["col"]):
            ic = ICONS.get(n["kind"], ".")
            if n["id"] == m.get("current"):
                cells.append(f"[{ic}]")       # where you are now
            elif n["accessible"] and not n["visited"]:
                cells.append(f"<{ic}>")       # a legal move
            elif n["visited"]:
                cells.append(f" {ic}'")       # already done
            else:
                cells.append(f" {ic} ")
        rows.append(f"  layer {layer:>2} | " + " ".join(cells))
    return "\n".join(rows)


def team_view(team: list[dict] | None) -> str:
    if not team:
        return "  (empty team)"
    rows = []
    for i, p in enumerate(team):
        filled = round((p["hp"] / p["max_hp"]) * 10) if p["max_hp"] else 0
        bar = "#" * max(0, filled) + "." * max(0, 10 - filled)
        item = f"  [{p['item']}]" if p.get("item") else ""
        shiny = " *" if p.get("shiny") else ""
        # Slot 0 leads the next battle.
        lead = "  <- leads" if i == 0 and len(team) > 1 else ""
        # The move the engine would use for this Pokemon.
        mv = p.get("move") or {}
        move = f"  {mv['name']} {mv.get('power', '?')}" if mv.get("name") else ""
        rows.append(
            f"  {i}. {p['name']:<13}Lv{p['level']:>2}  {bar} {p['hp']:>3}/{p['max_hp']:<3}"
            f"  {'/'.join(p.get('types') or [])}{move}{item}{shiny}{lead}"
        )
    return "\n".join(rows)


def actions_view(actions: list[dict]) -> str:
    """The numbered options. For map nodes, the tooltip (trainer type, gym roster,
    trade description) is appended when present.
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
    """The move tutor's offer compared against each team member's current move.

    Renders whenever offered_moves is present in the state (the bridge fills it
    unconditionally). Gating on the screen is the caller's job; screen() shows
    this block only on the tutor screen.
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


def screen(obs: dict[str, Any], with_legend: bool = False) -> str:
    """The whole turn as text."""
    run = obs.get("run") or {}
    head = (
        f"step {obs.get('steps', 0)}   screen: {obs.get('screen')}   "
        f"map {run.get('map', '-')}   badges {run.get('badges', '-')}"
    )
    parts = ["=" * 72, head, "=" * 72]
    if obs.get("prompt"):
        # The prompt disambiguates what the screen is asking.
        parts += ["", f'  >> {obs["prompt"]}']
    parts += ["", "TEAM", team_view(obs.get("team"))]

    bag = obs.get("bag") or []
    if bag:
        parts += ["", "BAG", "  " + ", ".join(str(b) for b in bag)]

    if obs.get("map"):
        parts += ["", "MAP   [here]  <legal move>  x'=done", map_view(obs["map"])]
        if with_legend:
            parts += ["", LEGEND]

    offers = tutor_view(obs) if obs.get("screen") == "move-tutor-screen" else ""
    if offers:
        parts += ["", "MOVE TUTOR, what each offer replaces", offers]

    parts += ["", "ACTIONS", actions_view(obs.get("actions") or [])]

    if obs.get("done"):
        parts += ["", ">>> RUN OVER <<<"]
    return "\n".join(parts)
