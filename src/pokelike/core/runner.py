"""Playing one run with a bot, in one place.

This loop used to exist three times — in `bench.py`, in the CLI, and in the
prompt comparison — which is the kind of duplication that does not announce
itself. Add a hook to `Bot` and you update two of the three copies; the third
quietly stops calling it, and nothing fails, it just does less.

It lives in the package rather than in `experiments/` because the package needs
it too: the benchmark and the `bot` command are built on it.
"""

from __future__ import annotations

from typing import Any

from .game import Game


# The engine's own name for a node is not always the clearest one to read.
# `question` is what the bundle calls it; what it means to a player is that the
# node is unknown until you step on it. The engine's name stays the action key —
# only the display changes, so logs read well without the encoding drifting.
DISPLAY_NAMES = {
    "question": "unknown",
    "move_tutor": "tutor",
    "evil_team": "evil-team",
}


def short_label(a: dict[str, Any]) -> str:
    """A compact name for an action, for logs and traces.

    Labels that carry row context read like "EQUIP — Ponyta Lv8 — empty — EQUIP".
    The informative half is the context, not the button word, so keep both: five
    identical "EQUIP" entries in a log tell you nothing about what was chosen.
    """
    if a.get("kind") == "node":
        # WITH the id, not only the kind. A layer often offers two nodes of the
        # same kind, and without it the trace read `["tutor","tutor"]` -- two
        # options a reader cannot tell apart, while the reason recorded beside them
        # argues about where each one LEADS. The bot was choosing between things it
        # could distinguish; only the log had stopped distinguishing them. This is
        # the same rule the button labels below already follow.
        kind = DISPLAY_NAMES.get(a["node"], a["node"])
        return f"{kind}#{a['id']}" if a.get("id") is not None else kind
    label = (a.get("label") or "").strip()

    # Row context: "EQUIP — Ponyta Lv8 — empty — EQUIP". The informative half is
    # the context, not the button word: five identical "EQUIP" entries in a log
    # say nothing about what was chosen.
    if "—" in label:
        parts = [p.strip() for p in label.split("—")]
        return f"{parts[0]}:{_name_and_level(parts[1])}"[:30]

    # A Pokemon card reads "Squirtle Lv. 5 WATER SP.A 10 SPE 9 HP 19 ...", and
    # the stats are already in `state["team"]` or on the catch screen. A log line
    # wants the identity, not the sheet.
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
) -> dict[str, Any]:
    """Plays one run start to finish and returns what happened.

    `on_step(obs, steps)` is called before each decision, which is how the CLI
    saves a screenshot per turn without this function knowing what a screenshot
    is. `on_decision(entry)` is called right after one, with the trace entry, so
    a log can stream as the run happens instead of arriving once it is over.

    The metrics come from `last_alive` rather than the final observation on
    purpose: at game over the engine wipes `state`, so the team and the badge
    count are gone by the time the run ends.
    """
    obs = game.reset(seed=seed)
    bot.on_start(seed)
    trace: list[dict[str, Any]] = []
    # `_settle` gives up after 90 seconds and flags the state rather than raising,
    # because one wedged turn should not throw away the runs already played. But
    # nothing read the flag, so a run that spent a minute and a half stuck looked
    # exactly like a run that ended. Carried out with the result instead.
    stalled = False

    while not obs.get("done") and obs.get("actions") and game.steps < max_steps:
        if obs.get("stalled"):
            stalled = True
        if on_step:
            on_step(obs, game.steps)

        # Free actions come first: reordering does not consume the turn, so the
        # state handed to `choose` must already show the team as the bot wants
        # it. A bot that does not implement the hook is unaffected.
        swapped = None
        if obs.get("can_reorder"):
            try:
                pick = bot.rearrange(obs)
            except Exception:  # noqa: BLE001
                pick = None
            if pick is not None:
                a, b = pick
                try:
                    obs = game.reorder(int(a), int(b))
                    swapped = [int(a), int(b)]
                except Exception:  # noqa: BLE001
                    # An illegal swap is the bot's mistake, not the run's: the
                    # turn still has a move to make, so play on and let the
                    # trace show that nothing moved.
                    swapped = None

        options = list(obs["actions"])
        chosen = bot.choose(obs)

        # Recorded for every bot alike, in the shared loop rather than in each
        # bot, so the log means the same thing whatever is playing.
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
            "why": (bot.explain() or "").strip(),
        })
        if on_decision:
            on_decision(trace[-1])

        obs = game.step(chosen)

    score = game.score() or {}
    bot.on_end(obs, score)

    breakdown = score.get("breakdown") or {}
    alive = game.last_alive or {}
    return {
        "seed": seed,
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
