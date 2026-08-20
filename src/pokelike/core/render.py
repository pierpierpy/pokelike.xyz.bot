"""Text rendering of the game state.

Everything here is rebuilt from `state`, a JavaScript object read as JSON. No
pixel is ever inspected: the map below is not read from an image, we draw it
ourselves from the nodes and edges.
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


# EVERYTHING STRUCTURAL HERE IS ASCII, AND THAT IS NOT LAZINESS.
#
# The pretty characters — ▶ ◀ · ╱ ╲ │ ─ ╭ ╰ — are all East Asian AMBIGUOUS
# width. Not one column, not two: whatever the terminal decided, and the process
# drawing them cannot find out. Mixed with two-column emoji they drifted a
# little further out of line on every row, which looked like a bug in the layout
# and was a property of the alphabet.
#
# So the grid is drawn with / \ | - + > < ( ) . — every one of them narrow by
# definition — and the only wide things are the emoji, which are unambiguously
# two columns. Alignment then follows from the character set instead of from a
# guess about the terminal.
#
# No library either: the engine gives every node a `layer` and a `col`, so there
# was no layout to compute, which is the only thing a graph library would have
# done. What was missing was the drawing.
# Every one of these is TWO columns wide, checked with east_asian_width. A mixed
# set is the worst case: `⚔` is one column while the rest are two, so the box
# edges and the edge lines drift apart by a character per node.
EMOJI = {
    "start": "🏁", "battle": "👊", "trainer": "🧢", "catch": "🔴", "item": "🎁",
    "pokecenter": "💊", "question": "❓", "trade": "🔄", "move_tutor": "📖",
    "boss": "👑", "shiny": "✨", "pokemart": "🛒", "mutation": "🧬",
    "evil_team": "💀", "silver": "⚪", "legendary": "🐉",
}

ANSI = {
    "here": "\033[1;96m",     # bright cyan, bold
    "open": "\033[1;92m",     # bright green: you may go there now
    "done": "\033[2;37m",     # dim: already walked
    "far": "\033[2;37m",
    "edge": "\033[2;37m",
    "frame": "\033[2;37m",
    "off": "\033[0m",
}


def _display_width(text: str) -> int:
    """Terminal columns, not characters.

    An emoji is one character and two columns. Padding by `len()` therefore
    leaves the right edge of a box short by one per glyph, which is exactly how
    the frame ends up ragged.
    """
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def graph_view(m: dict[str, Any] | None, colour: bool = True,
               emoji: bool = False) -> str:
    """The map as the graph it is, boxed, with you marked on it.

    `map_view` lists nodes layer by layer, which loses the two things that make
    the map a decision: they are not aligned by the column they sit in, and the
    EDGES are not drawn at all. Choosing a node closes every other one on its
    layer forever, so where a node LEADS matters as much as what it is.

    A node sits at column * 4, so a layer reads as a row and the gap under it
    carries the edges leaving it.
    """
    if not m or not m.get("nodes"):
        return "  (no map)"
    nodes = {n["id"]: n for n in m["nodes"] if n.get("revealed")}
    if not nodes:
        return "  (nothing revealed yet)"

    by_layer: dict[int, list[dict]] = {}
    for n in nodes.values():
        by_layer.setdefault(n["layer"], []).append(n)
    # An emoji is two terminal columns, so its cells and its spacing are wider.
    # The grid below is in DISPLAY columns, and a glyph simply occupies two of
    # them, which keeps the frame and the edges lined up.
    glyphs, gw, pitch = (EMOJI, 2, 6) if emoji else (ICONS, 1, 4)

    # Each layer is CENTRED, not left-aligned. The game's map is a diamond — the
    # layers widen and close again — and pinning every layer to column zero
    # throws that away, which is the shape of the choice: how many ways there
    # are from here, and how they converge.
    #
    # Positions are computed once and shared, so an edge is always drawn between
    # the two glyphs it actually connects.
    widest = max(len(v) for v in by_layer.values())
    span = (widest - 1) * pitch + gw + 4
    at: dict[str, int] = {}
    for layer, group in by_layer.items():
        group.sort(key=lambda n: n["col"])
        offset = (span - ((len(group) - 1) * pitch + gw)) // 2
        for k, n in enumerate(group):
            at[n["id"]] = offset + k * pitch
    edges = [(f, t) for f, t in (m.get("edges") or []) if f in nodes and t in nodes]

    def paint(text: str, kind: str) -> str:
        return f"{ANSI[kind]}{text}{ANSI['off']}" if colour else text

    rows: list[tuple[str, list[tuple[int, int, str]]]] = []
    for layer in sorted(by_layer):
        line = [" "] * span
        marks: list[tuple[int, int, str]] = []
        for n in by_layer[layer]:
            g = glyphs.get(n["kind"], "·")
            if n["id"] == m.get("current"):
                cell, kind = f">{g}<", "here"
            elif n.get("accessible") and not n.get("visited"):
                cell, kind = f"({g})", "open"
            elif n.get("visited"):
                # Marked in the TEXT, not only in the colour: a log piped to a
                # file has no colour, and the path already walked is most of
                # what makes the picture worth looking at.
                cell, kind = f".{g}.", "done"
            else:
                cell, kind = f" {g} ", "far"
            i = at[n["id"]] - 1
            # One list slot per DISPLAY column: a two-column glyph takes its own
            # slot plus a blank, so every later position still lines up.
            drawn = []
            for ch in cell:
                drawn.append(ch)
                if ch == g and gw == 2:
                    drawn.append("")
            line[i:i + len(drawn)] = drawn
            marks.append((i, len(drawn), kind))
        rows.append(("".join(line), marks))

        gap = [" "] * span
        drew = False
        for f, t in edges:
            a, b = nodes[f], nodes[t]
            if a["layer"] != layer or b["layer"] != layer + 1:
                continue
            ca, cb = at[a["id"]], at[b["id"]]
            # Halfway between the two glyph CENTRES, not between where they
            # start. A two-column emoji is centred half a column right of its
            # own position, so ignoring `gw` puts every connector half a
            # character to the left of where the eye expects it.
            gap[(ca + cb + gw - 1) // 2] = "|" if cb == ca else ("\\" if cb > ca else "/")
            drew = True
        if drew:
            rows.append(("".join(gap), [(0, span, "edge")]))

    inner = max(_display_width(r.rstrip()) for r, _ in rows) + 2

    # NO RIGHT-HAND BORDER, on purpose. Closing the box means every row has to
    # end at the same column, and the width of an emoji is not knowable from
    # here: `east_asian_width` says two, and terminals and fonts disagree. The
    # result was a right edge that landed somewhere different on every row.
    # Framing only the top, the bottom and the left asks nothing to line up.
    def framed(text: str, marks) -> str:
        padded = text.rstrip()
        if colour:
            out, last = [], 0
            for i, n, kind in sorted(marks):
                if i >= len(padded):
                    break
                out += [padded[last:i], paint(padded[i:i + n], kind)]
                last = i + n
            out.append(padded[last:])
            padded = "".join(out)
        return f"  {paint('|', 'frame')}{padded}"

    top = paint("+" + "-" * inner, "frame")
    bot = paint("+" + "-" * inner, "frame")
    legend = "  " + "  ".join([
        paint(">here<", "here"), paint("(can go)", "open"),
        paint(".walked.", "done"), paint(" unseen ", "far"),
    ])
    return "\n".join([f"  {top}", *[framed(t, mk) for t, mk in rows], f"  {bot}", legend])


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
    """The numbered options, with what the game says each one is.

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
    """The tutor's offer against what that Pokemon already uses.

    The buttons read "→ SURF:Wartortle Lv35" and carry neither power nor type,
    so the comparison that decides the choice is not on screen at all. It is in
    the state — `team[i].move` and `offered_moves[i]` — and this is where it
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

    offers = tutor_view(obs) if obs.get("screen") == "move-tutor-screen" else ""
    if offers:
        parts += ["", "MOVE TUTOR — what each offer replaces", offers]

    parts += ["", "ACTIONS", actions_view(obs.get("actions") or [])]

    if obs.get("done"):
        parts += ["", ">>> RUN OVER <<<"]
    return "\n".join(parts)


def score_view(s: dict[str, Any] | None) -> str:
    if not s:
        return "score not available"
    b = s.get("breakdown") or {}
    st = s.get("stats") or {}
    rows = [
        f"SCORE: {s.get('points')}   (without time bonus: {s.get('points_no_time')})",
        "",
        f"  win bonus           {b.get('winBonus', 0):>6}",
        f"  enemies knocked out {b.get('enemiesKO', 0):>6}  (x5)",
        f"  own faints          {b.get('faints', 0):>6}  (x-10)",
        f"  maps cleared        {b.get('mapsCleared', 0):>6}  (x50)",
        f"  legendaries         {b.get('legendaries', 0):>6}  (x20)",
        f"  shinies             {b.get('shinies', 0):>6}  (x20)",
        f"  time bonus          {b.get('timeBonus', 0):>6}",
        "",
        f"  battles won         {st.get('battlesWon', 0):>6}",
        f"  catches             {st.get('catches', 0):>6}",
        f"  damage dealt        {st.get('totalDamageDealt', 0):>6}",
        f"  damage taken        {st.get('totalDamageTaken', 0):>6}",
        f"  critical hits       {st.get('critHits', 0):>6}",
        f"  highest level       {st.get('highestLevel', 0):>6}",
    ]
    return "\n".join(rows)


def trace_line(t: dict[str, Any]) -> str:
    """One decision on one line. `>` marks what was taken, so no second column."""
    options = "  ".join(
        f"{'>' if i == t['chosen'] else ' '}{o}" for i, o in enumerate(t["options"])
    )
    swap = f" [swap {t['swapped'][0]}<->{t['swapped'][1]}]" if t.get("swapped") else ""
    return (f"  {t['step']:>3} {t['screen']:<17} b{t.get('badges', 0)} "
            f"m{t.get('map', 0)}{swap} | {options}")


def trace_view(trace: list[dict[str, Any]], detail: int = 1) -> str:
    """The log of a run.

    detail 1  one line per decision
    detail 2  a block per decision, with the bot's own explanation
    detail 3  and the team at every step

    Everything except the explanation is recorded by the shared run loop, so it
    reads the same whatever was playing. The explanation is empty for bots that
    have nothing to say — which is honest, not a gap.
    """
    if not trace:
        return "  (no decisions recorded)"
    if detail <= 1:
        return "\n".join(trace_line(t) for t in trace)
    with_team = detail >= 3
    out = []
    for t in trace:
        head = (f"  {t['step']:>3} | {t['screen']:<18} "
                f"map {t.get('map', '-')}  badges {t.get('badges', '-')}")
        out.append(head)
        # A swap happened before the choice and does not consume the turn, so it
        # is shown above the options rather than as one of them.
        if t.get("swapped"):
            a, b = t["swapped"]
            out.append(f"      | swap slots {a} <-> {b}, {t.get('team', ['?'])[0]} now leads"
                       if t.get("team") else f"      | swap slots {a} <-> {b}")
        if with_team and t.get("team"):
            out.append(f"      | team: {', '.join(t['team'])}")
        marked = [
            f"[{i}]{'*' if i == t['chosen'] else ' '}{o}"
            for i, o in enumerate(t["options"])
        ]
        out.append(f"      | {'  '.join(marked)}")
        out.append(f"      | -> {t['chosen_label']}")
        if t.get("why"):
            out.append(f"      |    {t['why'][:110]}")
        out.append("")
    return "\n".join(out)


def ending_view(final: dict[str, Any], alive: dict[str, Any] | None,
                score: dict[str, Any] | None) -> str:
    """What the last decision led to.

    The trace stops one move short by construction: it records a decision and
    then takes it, so the state that decision produced is only ever visible as
    the header of the NEXT entry — and the last one has no next. So a log of a
    losing run showed every choice and never the death.

    Reads the team from `last_alive`, because at game over the engine wipes
    `state` and the final observation has an empty team.
    """
    ended = final.get("screen") or "?"
    won = ended == "win-screen"
    run = (alive or {}).get("run") or {}
    out = ["", f"  === run over: {ended} ==="]
    out.append(f"      | {'the League is beaten' if won else 'the run ended here'}"
               f"  —  badges {run.get('badges', 0)}, map {run.get('map', 0)}")

    # NOT the final team. At game over the engine wipes `state`, so this is the
    # last snapshot taken while it was still populated — which is from BEFORE
    # whatever ended the run. Saying "the team is out" over three Pokemon at 60%
    # HP would be inventing a cause of death the log does not know.
    team = (alive or {}).get("team") or []
    if team:
        out.append("      | team as of the last snapshot (before the final fight):")
        for i, p in enumerate(team):
            frac = p["hp"] / p["max_hp"] if p["max_hp"] else 0
            state = "fainted" if p["hp"] == 0 else f"{p['hp']}/{p['max_hp']}"
            lead = " (led)" if i == 0 else ""
            out.append(f"      |   {i}. {p['name']:<13}Lv{p['level']:<3} {state:>9}"
                       f"{'  <- weak' if 0 < frac < 0.35 else ''}{lead}")

    b = (score or {}).get("breakdown") or {}
    if b:
        out.append(f"      | {b.get('enemiesKO', 0)} enemies KO'd, "
                   f"{b.get('faints', 0)} of yours fainted  ->  "
                   f"5x{b.get('enemiesKO', 0)} - 10x{b.get('faints', 0)} = "
                   f"{(score or {}).get('points_no_time')}")
    out.append("")
    return "\n".join(out)
