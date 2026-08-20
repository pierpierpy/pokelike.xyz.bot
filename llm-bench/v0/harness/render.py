"""Text rendering of the game state, frozen beside the harness that uses it.

A COPY of the part of `pokelike.core.render` this harness renders with, not an
import of it. Same reason `bot.py` is a copy: the shared module is meant to
improve, because the CLI reads it and so do the bots in `bots/`, and a benchmark
needs the opposite. If this file imported that one, the next improvement made
for a person reading a terminal would silently change what every recorded score
on this harness meant.

So it is never edited once a result exists beside it. A new idea is a new
harness directory, and the rows already recorded stay valid under the version
that earned them.

What is here is what the harness calls, and nothing else: `screen()` and
`team_view()`, plus the three block renderers and the two tables `screen()`
needs. The shared module also carries `graph_view` (the drawn map), plus
`score_view`, `trace_view` and `ending_view`. Those are read by a person at a
terminal and by nothing in here, so copying them would have been 300 lines of
code this file cannot reach.

Everything is rebuilt from `state`, a JavaScript object read as JSON. No pixel is
ever inspected: the map below is not read from an image, we draw it ourselves
from the nodes and edges.
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
        # Slot 0 is the Pokemon that enters the next battle. The numbers were
        # already here but read as decoration; saying so makes the order legible
        # as the decision it is.
        lead = "  <- leads" if i == 0 and len(team) > 1 else ""
        # What it actually attacks with. The engine knows; nothing on screen says
        # it, so a player reading only the terminal was choosing blind too.
        mv = p.get("move") or {}
        move = f"  {mv['name']} {mv.get('power', '?')}" if mv.get("name") else ""
        rows.append(
            f"  {i}. {p['name']:<13}Lv{p['level']:>2}  {bar} {p['hp']:>3}/{p['max_hp']:<3}"
            f"  {'/'.join(p.get('types') or [])}{move}{item}{shiny}{lead}"
        )
    return "\n".join(rows)


def actions_view(actions: list[dict]) -> str:
    if not actions:
        return "  (no actions)"
    rows = []
    for i, a in enumerate(actions):
        if a["kind"] == "node":
            rows.append(f"  [{i}] go to node {a['id']:<6} ({a['node']})")
        else:
            rows.append(f"  [{i}] {a['label']}")
    return "\n".join(rows)


def tutor_view(obs: dict[str, Any]) -> str:
    """The tutor's offer against what that Pokemon already uses.

    The buttons read "→ SURF:Wartortle Lv35" and carry neither power nor type,
    so the comparison that decides the choice is not on screen at all. It is in
    the state — `team[i].move` and `offered_moves[i]` — and this is where it
    becomes readable.
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
        # What the screen is asking. Without it, "pick one of your team" is
        # ambiguous between promoting and releasing.
        parts += ["", f'  >> {obs["prompt"]}']
    parts += ["", "TEAM", team_view(obs.get("team"))]

    bag = obs.get("bag") or []
    if bag:
        parts += ["", "BAG", "  " + ", ".join(str(b) for b in bag)]

    if obs.get("map"):
        parts += ["", "MAP   [here]  <legal move>  x'=done", map_view(obs["map"])]
        if with_legend:
            parts += ["", LEGEND]

    offers = tutor_view(obs)
    if offers:
        parts += ["", "MOVE TUTOR — what each offer replaces", offers]

    parts += ["", "ACTIONS", actions_view(obs.get("actions") or [])]

    if obs.get("done"):
        parts += ["", ">>> RUN OVER <<<"]
    return "\n".join(parts)
