"""Whole-screen composition and trace rendering.

Assembles a full turn view from the parts, and formats decision logs.
"""

from __future__ import annotations

from typing import Any

from .actions import actions_view, tutor_view
from .team import team_view
from .world import LEGEND, map_view


def screen(obs: dict[str, Any], with_legend: bool = False) -> str:
    """Renders an entire turn as one text block.

    This function takes the observation dict from `Game.state()` and returns
    the full printable view.
    """
    run = obs.get("run") or {}
    head = (
        f"step {obs.get('steps', 0)}   screen: {obs.get('screen')}   "
        f"map {run.get('map', '-')}   badges {run.get('badges', '-')}"
        # Shown only when the region differs from the default (Kanto).
        + (f"   region: {obs['region']}" if obs.get("region") not in (None, "kanto") else "")
    )
    parts = ["=" * 72, head, "=" * 72]
    if obs.get("prompt"):
        # What the screen is asking. Without the prompt, "pick one of your team"
        # is ambiguous between promoting and releasing.
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


def trace_line(t: dict[str, Any]) -> str:
    """Formats one decision as a single line.

    This function takes one trace entry dict and returns a compact one-line
    summary.

    The `>` marker indicates what was taken, so no second column is needed.
    """
    options = "  ".join(
        f"{'>' if i == t['chosen'] else ' '}{o}" for i, o in enumerate(t["options"])
    )
    swap = f" [swap {t['swapped'][0]}<->{t['swapped'][1]}]" if t.get("swapped") else ""
    return (f"  {t['step']:>3} {t['screen']:<17} b{t.get('badges', 0)} "
            f"m{t.get('map', 0)}{swap} | {options}")


def trace_view(trace: list[dict[str, Any]], detail: int = 1) -> str:
    """Formats the log of a run at the chosen detail level.

    This function takes the trace list and a detail level (1-3), and returns
    the formatted log.

    detail 1: one line per decision
    detail 2: a block per decision, with the bot's own explanation
    detail 3: and the team at every step

    Everything except the explanation is recorded by the shared run loop, so
    the format is the same regardless of which bot played.
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
    """Formats the end-of-run summary.

    This function takes the final obs, the last-alive snapshot, and the score
    dict, and returns the summary block.

    The team is read from `last_alive` because at game over the engine wipes
    `state` and the final observation has an empty team.
    """
    ended = final.get("screen") or "?"
    won = ended == "win-screen"
    run = (alive or {}).get("run") or {}
    out = ["", f"  === run over: {ended} ==="]
    out.append(f"      | {'the League is beaten' if won else 'the run ended here'}"
               f":  badges {run.get('badges', 0)}, map {run.get('map', 0)}")

    # The team here is from last_alive (before the fatal fight) because the
    # engine wipes the team at game over.
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
