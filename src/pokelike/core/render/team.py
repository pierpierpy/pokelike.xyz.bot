"""Team, bag and score rendering.

Pure functions that turn a team list or a score dict into printable text.
"""

from __future__ import annotations

from typing import Any


def team_view(team: list[dict] | None) -> str:
    """Draws the team as a table.

    In: the `team` list from a state. Out: the printable block, one line per slot.
    """
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
        # The move the Pokemon actually attacks with (not shown in-game).
        mv = p.get("move") or {}
        move = f"  {mv['name']} {mv.get('power', '?')}" if mv.get("name") else ""
        rows.append(
            f"  {i}. {p['name']:<13}Lv{p['level']:>2}  {bar} {p['hp']:>3}/{p['max_hp']:<3}"
            f"  {'/'.join(p.get('types') or [])}{move}{item}{shiny}{lead}"
        )
    return "\n".join(rows)


def score_view(s: dict[str, Any] | None) -> str:
    """Formats a score breakdown as a readable table.

    In: the score dict from `Game.score()`. Out: the formatted score block.
    """
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
