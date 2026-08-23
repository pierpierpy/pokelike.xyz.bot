"""Playing one run with a bot, in one place.

The `play_run` function is the single loop that plays a full run. The benchmark,
the CLI, and the bot commands all use it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .browser import REGIONS, normalise_region, region_name
from .game import Game


# Friendlier display names for node types in traces and logs.
DISPLAY_NAMES = {
    "question": "unknown",
    "move_tutor": "tutor",
    "evil_team": "evil-team",
}


def short_label(a: dict[str, Any]) -> str:
    """Returns a compact name for an action, for logs and traces."""
    if a.get("kind") == "node":
        # Include the id because a layer can offer two nodes of the same kind.
        kind = DISPLAY_NAMES.get(a["node"], a["node"])
        return f"{kind}#{a['id']}" if a.get("id") is not None else kind
    label = (a.get("label") or "").strip()

    # For row-context labels, keep the contextual part (e.g. "EQUIP:Ponyta Lv8").
    if "—" in label:
        parts = [p.strip() for p in label.split("—")]
        return f"{parts[0]}:{_name_and_level(parts[1])}"[:30]

    # A Pokemon card label has the full stat line; just keep name and level.
    short = _name_and_level(label)
    return short[:30] or f"slot{a.get('idx', 0)}"


_POKEMON = None


def _name_and_level(text: str) -> str:
    global _POKEMON
    if _POKEMON is None:
        import re

        _POKEMON = re.compile(r"^([A-Za-z][\w'.-]*)\s+Lv\.?\s*(\d+)")
    m = _POKEMON.match(text.strip())
    return f"{m.group(1)} Lv{m.group(2)}" if m else text.strip()


def play_run(
    game: Game,
    bot: Any,
    seed: int,
    max_steps: int = 400,
    on_step=None,
    on_decision=None,
    region: int | str = 1,
) -> dict[str, Any]:
    """Plays one run start to finish and returns what happened.

    `on_step(obs, steps)` fires before each decision. `on_decision(entry)` fires
    after each decision with the trace entry. Metrics come from `last_alive`
    because the engine wipes state at game over.
    """
    obs = game.reset(seed=seed, region=region)
    bot.reset(seed)
    trace: list[dict[str, Any]] = []
    # Track if _settle ever timed out, so the result can report the stall.
    stalled = False

    while not obs.get("done") and obs.get("actions") and game.steps < max_steps:
        if obs.get("stalled"):
            stalled = True
        if on_step:
            on_step(obs, game.steps)

        # Reorder first because reordering does not consume the turn, so act() sees the final order.
        swapped = None
        if obs.get("can_reorder"):
            try:
                pick = bot.reorder(obs)
            except Exception:  # noqa: BLE001
                pick = None
            if pick is not None:
                a, b = pick
                try:
                    obs = game.reorder(int(a), int(b))
                    swapped = [int(a), int(b)]
                except Exception:  # noqa: BLE001
                    # An illegal swap is non-fatal; the turn still proceeds.
                    swapped = None

        options = list(obs["actions"])
        chosen = bot.act(obs)

        # The trace entry is recorded here (not in the bot) so the log format
        # is identical regardless of which bot is playing.
        run = obs.get("run") or {}
        team = obs.get("team") or []
        trace.append({
            "step": game.steps,
            "screen": obs.get("screen"),
            "map": run.get("map"),
            "badges": run.get("badges"),
            "team": [f"{p['name']} L{p['level']} {p['hp']}/{p['max_hp']}" for p in team],
            "options": [short_label(a) for a in options],
            "chosen": chosen,
            "chosen_label": short_label(options[chosen]) if 0 <= chosen < len(options) else "?",
            "swapped": swapped,
            "why": (bot.reason() or "").strip(),
        })
        if on_decision:
            on_decision(trace[-1])

        obs = game.step(chosen)

    score = game.score() or {}
    bot.finish(obs, score)

    breakdown = score.get("breakdown") or {}
    alive = game.last_alive or {}
    return {
        "seed": seed,
        "region": obs.get("region") or region_name(normalise_region(region)),
        "steps": game.steps,
        "score": score.get("points_no_time"),
        "score_raw": score.get("points"),
        "badges": (alive.get("run") or {}).get("badges", 0),
        "maps": breakdown.get("mapsCleared", 0),
        "kos": breakdown.get("enemiesKO", 0),
        "faints": breakdown.get("faints", 0),
        "ending": obs.get("screen"),
        "stalled": stalled or bool(obs.get("stalled")),
        "team": alive.get("team") or [],
        "final_state": obs,
        "score_detail": score,
        "trace": trace,
    }


def play_campaign(
    game: Game,
    bot: Any,
    seed: int,
    regions: Sequence[int | str] | None = None,
    max_steps: int = 400,
    on_step=None,
    on_decision=None,
    on_region=None,
) -> dict[str, Any]:
    """Plays regions in sequence with the same bot, stopping at the first loss.

    Returns one result covering the whole campaign, with per-region results
    under `regions`.
    """
    # Each region is a full independent game (new starter, badge count resets).
    # Only the bot's memory crosses. The campaign stops at the first region not won.
    order = list(regions or REGIONS)
    runs: list[dict[str, Any]] = []
    opening: str | None = None

    for i, region in enumerate(order):
        if opening is not None and hasattr(bot, "region_opening"):
            bot.region_opening(opening)
        run = play_run(game, bot, seed=seed, max_steps=max_steps,
                       on_step=on_step, on_decision=on_decision, region=region)
        runs.append(run)
        won = run.get("ending") == "win-screen"
        done = {
            "region": run["region"],
            "next": (region_name(normalise_region(order[i + 1]))
                     if won and i + 1 < len(order) else None),
            "badges": run.get("badges", 0),
            "won": won,
            "steps": run.get("steps", 0),
            "team": [f"{p.get('name')} L{p.get('level')}" for p in (run.get("team") or [])],
        }
        if on_region is not None:
            on_region(done)
        if not won or done["next"] is None:
            break
        # This is called before reset_memory so the bot still has the region's context.
        opening = bot.region_cleared(done)
        bot.reset_memory()

    def total_of(key: str) -> int:
        return sum(r.get(key) or 0 for r in runs)

    # Start from the last region's result and override with campaign totals.
    # Fields about where the campaign ended (region, final_state, team, ending)
    # come from the last run; numeric fields are summed across all regions.
    out = dict(runs[-1]) if runs else {}
    out.update({
        "seed": seed,
        "badges": total_of("badges"),
        "steps": total_of("steps"),
        "score": total_of("score"),
        "score_raw": total_of("score_raw"),
        "maps": total_of("maps"),
        "kos": total_of("kos"),
        "faints": total_of("faints"),
        "stalled": any(r.get("stalled") for r in runs),
        "regions": runs,
        "regions_played": len(runs),
        "regions_cleared": sum(1 for r in runs if r.get("ending") == "win-screen"),
        # The flattened trace tags each entry with its region for readability.
        "trace": [{**e, "region": r["region"]} for r in runs
                  for e in (r.get("trace") or [])],
    })
    return out
