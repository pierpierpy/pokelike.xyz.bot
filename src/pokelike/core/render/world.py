"""Map and graph rendering.

Pure functions that draw the game map as ASCII (compact list or full graph).
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

# EVERYTHING STRUCTURAL HERE IS ASCII, AND THAT IS NOT LAZINESS.
#
# The pretty characters (▶ ◀ · ╱ ╲ │ ─ ╭ ╰) are all East Asian AMBIGUOUS
# width. Not one column, not two: whatever the terminal decided, and the process
# drawing them cannot find out. Mixed with two-column emoji they drifted a
# little further out of line on every row, which looked like a bug in the layout
# and was a property of the alphabet.
#
# So the grid is drawn with / \ | - + > < ( ) . (every one of them narrow by
# definition) and the only wide things are the emoji, which are unambiguously
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


def map_view(m: dict[str, Any] | None) -> str:
    """Draws the compact layer-by-layer map.

    In: the `map` dict from a state. Out: the printable map block.
    """
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


def _display_width(text: str) -> int:
    """Counts terminal columns (not characters) for alignment.

    In: a string. Out: the display width in terminal columns.

    An emoji is one character and two columns. Padding by `len()` therefore
    leaves the right edge of a box short by one per glyph, which is exactly how
    the frame ends up ragged.
    """
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def graph_view(m: dict[str, Any] | None, colour: bool = True,
               emoji: bool = False) -> str:
    """The map as the graph it is, boxed, with the player marked on it.

    In: the `map` dict, colour flag, emoji flag. Out: the printable graph view.

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

    # Each layer is CENTRED, not left-aligned. The game's map is a diamond (the
    # layers widen and close again) and pinning every layer to column zero
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


def exits_of(state: dict[str, Any], unique: bool = False) -> dict[int, list[str]]:
    """Where each legal option leads on the next layer.

    In: a state, and whether to collapse repeats. Out: {option index: the kinds of
    node it leads to}, with options that are not map moves left out.
    """
    # The map is a graph: `nodes` have kinds, `edges` are (from, to) pairs. Walking
    # them is what tells you that picking one node opens a pokecenter and picking the
    # other does not, which is the whole reason to look before choosing. Written once
    # here because every LLM bot wants it and two copies had already drifted.
    world = state.get("map") or {}
    kind_of = {node["id"]: node["kind"] for node in world.get("nodes") or []}

    leads_to: dict[str, list[str]] = {}
    for source, target in world.get("edges") or []:
        if target in kind_of:
            leads_to.setdefault(source, []).append(kind_of[target])

    exits: dict[int, list[str]] = {}
    for index, option in enumerate(state.get("actions") or []):
        if option.get("kind") != "node":
            continue                      # a button, not a step on the map
        kinds = leads_to.get(option.get("id"), [])
        exits[index] = sorted(set(kinds)) if unique else sorted(kinds)
    return exits
