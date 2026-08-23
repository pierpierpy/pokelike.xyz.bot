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

# The grid uses only ASCII structural characters (/ \ | - + > < ( ) .) because
# the "ambiguous width" Unicode characters (▶ ◀ · ╱ ╲ │ ─ ╭ ╰) cannot be
# reliably measured in a terminal, and mixing them with two-column emoji breaks
# alignment. The only wide characters are the emoji themselves, which are
# unambiguously two columns.
#
# No graph library is needed because the engine gives every node a `layer` and
# a `col`, so there is no layout to compute.

# Every one of these is two columns wide (east_asian_width W or F). Mixing
# widths breaks alignment, so the full set must be uniform.
EMOJI = {
    "start": "🏁", "battle": "👊", "trainer": "🧢", "catch": "🔴", "item": "🎁",
    "pokecenter": "💊", "question": "❓", "trade": "🔄", "move_tutor": "📖",
    "boss": "👑", "shiny": "✨", "pokemart": "🛒", "mutation": "🧬",
    "evil_team": "💀", "silver": "⚪", "legendary": "🐉",
}

ANSI = {
    "here": "\033[1;96m",     # bright cyan, bold
    "open": "\033[1;92m",     # bright green, marks nodes you may go to now
    "done": "\033[2;37m",     # dim, marks already-walked nodes
    "far": "\033[2;37m",
    "edge": "\033[2;37m",
    "frame": "\033[2;37m",
    "off": "\033[0m",
}


def map_view(m: dict[str, Any] | None) -> str:
    """Draws the compact layer-by-layer map.

    This function takes the `map` dict from a state and returns the printable
    map block.
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
    """Counts terminal display columns for alignment.

    An emoji is one character but two columns; padding by `len()` misaligns
    the frame by one per glyph.
    """
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def graph_view(m: dict[str, Any] | None, colour: bool = True,
               emoji: bool = False) -> str:
    """The map as a boxed graph with the player marked, edges drawn.

    This function takes the `map` dict, a colour flag, and an emoji flag, and
    returns the printable graph view.

    Unlike `map_view`, this aligns nodes by their column position and draws the
    edges between layers, so the reader can see where each choice leads.
    """
    if not m or not m.get("nodes"):
        return "  (no map)"
    nodes = {n["id"]: n for n in m["nodes"] if n.get("revealed")}
    if not nodes:
        return "  (nothing revealed yet)"

    by_layer: dict[int, list[dict]] = {}
    for n in nodes.values():
        by_layer.setdefault(n["layer"], []).append(n)
    # An emoji occupies two terminal columns, so cells and spacing are wider
    # in emoji mode. The grid is in display columns.
    glyphs, gw, pitch = (EMOJI, 2, 6) if emoji else (ICONS, 1, 4)

    # Each layer is centred so the diamond shape of the map is preserved.
    # Positions are computed once and shared with edge drawing.
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
                # Visited nodes are marked in text (not only colour) so piped-to-file
                # output still shows the walked path.
                cell, kind = f".{g}.", "done"
            else:
                cell, kind = f" {g} ", "far"
            i = at[n["id"]] - 1
            # One list slot per display column; a two-column glyph takes its
            # slot plus a blank so later positions stay aligned.
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
            # This computes the midpoint between the two glyph centres, accounting for glyph width.
            gap[(ca + cb + gw - 1) // 2] = "|" if cb == ca else ("\\" if cb > ca else "/")
            drew = True
        if drew:
            rows.append(("".join(gap), [(0, span, "edge")]))

    inner = max(_display_width(r.rstrip()) for r, _ in rows) + 2

    # There is no right-hand border because emoji display width varies across
    # terminals and fonts, so a closed box would not align. Only the top, bottom,
    # and left sides are framed.
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
    """Where each legal map-move option leads on the next layer.

    This function takes a state and a flag for collapsing repeats, and returns
    a dict mapping option index to the list of node kinds that option leads to.
    Non-node actions are omitted.
    """
    # Walk the graph edges to find what kinds of node each choice opens.
    world = state.get("map") or {}
    kind_of = {node["id"]: node["kind"] for node in world.get("nodes") or []}

    leads_to: dict[str, list[str]] = {}
    for source, target in world.get("edges") or []:
        if target in kind_of:
            leads_to.setdefault(source, []).append(kind_of[target])

    exits: dict[int, list[str]] = {}
    for index, option in enumerate(state.get("actions") or []):
        if option.get("kind") != "node":
            continue                      # a UI button, skip it
        kinds = leads_to.get(option.get("id"), [])
        exits[index] = sorted(set(kinds)) if unique else sorted(kinds)
    return exits
