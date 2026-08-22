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

THREE THINGS DIFFER FROM THE COPY UNDER v0, v1 AND v2:

  1. `actions_view` prints each node's `tooltip`, the text the game shows a person
     resting the pointer on it: the trainer's archetype and which types they use, a
     gym leader's roster with levels, what a trade does. Under v0 to v2 the state
     did not carry it at all, so those runs are not comparable to these.

  2. `screen` shows the MOVE TUTOR block only on the tutor screen. Under v0 to v2
     it appeared on EVERY turn, because the bridge fills `offered_moves`
     unconditionally and nothing gated on the screen. 187 characters a turn, about
     58k tokens across a pass, describing an exchange that was not on offer. Those
     rows keep the old behaviour, which is why their copy keeps it too.

  3. `screen` shows `obs["region"]` in the header when it is not kanto, so a model
     in a later region can read which one it is in. Kanto is omitted so a pass that
     never leaves it renders byte-identically to v5.

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
        # What it actually attacks with, AND with what. v0-v4 showed the move's
        # name and power but not its TYPE, so the one fact that decides a battle
        # -- does this move's type beat what is in front of it -- was missing. Now
        # it carries the type, whether it is physical or special, and STAB (a
        # move matching the user's own type hits harder).
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
    """Where a map node leads on the next layer, read from the graph's edges.

    Folded into the view so the model sees the consequence of an irreversible
    choice without spending a tool round on `what_lies_ahead`: picking a node
    closes the others on that layer for good, and which KINDS of node it opens up
    next is what makes one option worth more than another.
    """
    if not m or not m.get("edges") or a.get("id") is None:
        return ""
    by_id = {n["id"]: n for n in m["nodes"]}
    after = sorted({by_id[t]["kind"] for f, t in m["edges"]
                    if f == a["id"] and t in by_id})
    return f"  -> next: {', '.join(after)}" if after else ""


def actions_view(actions: list[dict], m: dict[str, Any] | None = None) -> str:
    """The numbered options, with what the game says each one is.

    The `tooltip` is the text the game puts on screen when the pointer rests on
    that node: the trainer's archetype and which types they use, a gym leader's
    roster with levels, what a trade does. Someone playing in a browser reads it
    before choosing, so a terminal that left it out was the poorer view, not the
    equal one.

    v5 also appends where each node LEADS on the next layer (`-> next: ...`), the
    connectivity that was only reachable through the `what_lies_ahead` tool
    before.

    Absent on anything that is not a map node, and absent on older recordings,
    hence the `.get`.
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
    """The tutor's offer against what that Pokemon already uses.

    The buttons read "→ SURF:Wartortle Lv35" and carry neither power nor type,
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
    """The whole turn as text."""
    run = obs.get("run") or {}
    head = (
        f"step {obs.get('steps', 0)}   screen: {obs.get('screen')}   "
        f"map {run.get('map', '-')}   badges {run.get('badges', '-')}"
        # Only when it is not the default, so a Kanto pass renders as v5 does
        # and the header stays short for the common case.
        + (f"   region: {obs['region']}" if obs.get("region") not in (None, "kanto") else "")
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

    offers = tutor_view(obs) if obs.get("screen") == "move-tutor-screen" else ""
    if offers:
        parts += ["", "MOVE TUTOR, what each offer replaces", offers]

    parts += ["", "ACTIONS", actions_view(obs.get("actions") or [], obs.get("map"))]

    if obs.get("done"):
        parts += ["", ">>> RUN OVER <<<"]
    return "\n".join(parts)
