"""Text rendering of the game state, frozen beside the harness that uses it.

This is a copy of the relevant part of pokelike.core.render, rather than an import
of the shared module. The shared module evolves for the CLI and for bots in bots/,
while a benchmark needs the file to stay fixed. This file is never edited once a
result exists beside it.

This file provides screen() and team_view(), plus their building blocks (map_view,
actions_view, tutor_view). Everything is rebuilt from the state dict (a JavaScript
object read as JSON), and no pixels are inspected.

Differences from v0-v4: The actions_view function includes node tooltips. The move
tutor block renders only on the tutor screen. The header shows obs["region"] when the
region is not Kanto. Each action shows where it leads on the next layer.
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
        # Move type, physical/special, and STAB are the facts that decide a battle.
        mv = p.get("move") or {}
        move = ""
        if mv.get("name"):
            cat = "sp" if mv.get("special") else "ph"
            stab = " STAB" if mv.get("type") in (p.get("types") or []) else ""
            move = f"  {mv['name']} {mv.get('power', '?')} {mv.get('type', '?')}({cat}){stab}"
        rows.append(
            f"  {i}. {p['name']:<13}Lv{p['level']:>2}  {bar} {p['hp']:>3}/{p['max_hp']:<3}"
            f"  {'/'.join(p.get('types') or [])}{move}{item}{shiny}{lead}"
        )
    return "\n".join(rows)


def _exits_of(a: dict, m: dict[str, Any] | None) -> str:
    """Returns the kinds of node a map action leads to on the next layer.

    The result is shown inline so the model sees the consequence of an irreversible
    choice without spending a tool round.
    """
    if not m or not m.get("edges") or a.get("id") is None:
        return ""
    by_id = {n["id"]: n for n in m["nodes"]}
    after = sorted({by_id[t]["kind"] for f, t in m["edges"]
                    if f == a["id"] and t in by_id})
    return f"  -> next: {', '.join(after)}" if after else ""


def actions_view(actions: list[dict], m: dict[str, Any] | None = None) -> str:
    """Renders the numbered options.

    Each node shows its tooltip (trainer types, gym roster, trade details) and
    where it leads on the next layer.
    """
    if not actions:
        return "  (no actions)"
    rows = []
    for i, a in enumerate(actions):
        if a["kind"] == "node":
            tip = f"  {a['tooltip']}" if a.get("tooltip") else ""
            rows.append(f"  [{i}] go to node {a['id']:<6} ({a['node']}){tip}{_exits_of(a, m)}")
        else:
            rows.append(f"  [{i}] {a['label']}")
    return "\n".join(rows)


def tutor_view(obs: dict[str, Any]) -> str:
    """Compares each team member's current move against the tutor's offer.

    This function renders whenever offered_moves is present (the bridge fills the
    field unconditionally). Gating on the correct screen is the caller's job, and
    screen() only shows this block on the tutor screen.
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
        ncat = "sp" if new.get("special") else "ph"
        nstab = " STAB" if new.get("type") in (p.get("types") or []) else ""
        rows.append(
            f"  {i}. {p['name']:<13}"
            f"{cur.get('name', '?')} {cur.get('type', '?')} {cur.get('power', '?')}"
            f"  ->  {new['name']} {new.get('type', '?')}({ncat}) {new.get('power', '?')}"
            f"  {arrow}{gain if gain else ''}{nstab}"
        )
    return "\n".join(rows)


def screen(obs: dict[str, Any], with_legend: bool = False) -> str:
    """Renders the whole turn as text."""
    run = obs.get("run") or {}
    head = (
        f"step {obs.get('steps', 0)}   screen: {obs.get('screen')}   "
        f"map {run.get('map', '-')}   badges {run.get('badges', '-')}"
        # The region is only shown when not Kanto, keeping the common case short.
        + (f"   region: {obs['region']}" if obs.get("region") not in (None, "kanto") else "")
    )
    parts = ["=" * 72, head, "=" * 72]
    if obs.get("prompt"):
        # Shows what the screen is asking (e.g. "choose a Pokemon to release").
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

    parts += ["", "ACTIONS", actions_view(obs.get("actions") or [], obs.get("map"))]

    if obs.get("done"):
        parts += ["", ">>> RUN OVER <<<"]
    return "\n".join(parts)
