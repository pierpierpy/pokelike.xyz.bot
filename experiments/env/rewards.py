"""This module provides reward functions, selectable by name.

The choice of reward matters more here than the choice of algorithm, and this
file exists so that claim can be tested rather than asserted. Train the same
Dyna-Q with different rewards, compare them on the same metric, and see which
one actually produces a better player.

A reward function receives the transition and returns a float:

    reward(before, after, done, won) -> float

where `before` and `after` are observations (the full state dicts), so a reward
is free to look at anything:

  * the engine's counters
  * the badges
  * the team
  * how deep on the map you are


Why the game's own formula is a poor objective here
---------------------------------------------------
The engine's score is

    500·completed + 5·KO − 10·faints + 50·mapsCleared + 20·legendaries
    + 20·shinies + timeBonus

and it was written for the Battle Tower, not for Story mode. Two of its terms
are dead in a Story run:

  * `mapsCleared` is incremented in exactly one place in the bundle, inside
    `bumpEndlessCounters()`, which only runs on the endless path. In Story it
    stays 0 forever, so the +50 never fires.
  * `winBonus` needs the whole League beaten, which essentially never happens.

What is left is `5·KO − 10·faints`, which rewards fighting and punishes dying but
says nothing at all about getting further. Badges, the thing Story mode is
actually about, do not appear in the formula.

That is why a run with three badges can score −5, and why `game` below is kept
mainly as the honest baseline to measure the others against.
"""

from __future__ import annotations

from typing import Any, Callable

Observation = dict[str, Any]
RewardFn = Callable[[Observation | None, Observation | None, bool, bool], float]


def _stats(obs: Observation | None) -> dict:
    return (obs or {}).get("stats") or {}


def _run(obs: Observation | None) -> dict:
    return (obs or {}).get("run") or {}


def _delta(before: Observation | None, after: Observation | None, field: str) -> float:
    return (_stats(after).get(field) or 0) - (_stats(before).get(field) or 0)


def _depth(obs: Observation | None) -> int:
    """Returns the layer of the current map the player is standing on."""
    m = (obs or {}).get("map")
    if not m or not m.get("current"):
        return 0
    return next((n["layer"] for n in m["nodes"] if n["id"] == m["current"]), 0)


# --------------------------------------------------------------------- rewards


def game(before, after, done=False, won=False) -> float:
    """Applies the engine's own weights per step, faithful but nearly blind in Story mode.

    This function is kept as the baseline. If a shaped reward cannot beat this,
    the shaping was not worth the complexity.
    """
    r = 5 * _delta(before, after, "enemiesKO")
    r += -10 * _delta(before, after, "faintsSuffered")
    r += 50 * _delta(before, after, "mapsCleared")
    if done and won:
        r += 500
    return r


def badges(before, after, done=False, won=False) -> float:
    """Only progression matters here; a badge is worth a hundred faints, almost.

    This reward is extremely sparse. A whole run produces one or two nonzero
    rewards, which is close to nothing for a tabular method to learn from. The
    function is included so that sparsity can be seen rather than argued about.
    """
    r = 100 * ((_run(after).get("badges") or 0) - (_run(before).get("badges") or 0))
    r += -10 * _delta(before, after, "faintsSuffered")
    if done and won:
        r += 500
    return r


def progress(before, after, done=False, won=False) -> float:
    """Rewards badges, plus a small payment for every step deeper into the map.

    The map is a DAG, so you cannot farm this by going in circles because every
    node visited really is progress. That turns the sparse badge signal into a
    dense one, which is the textbook fix for a long chain of decisions ending in
    a single distant payout.
    """
    r = 100 * ((_run(after).get("badges") or 0) - (_run(before).get("badges") or 0))
    r += -10 * _delta(before, after, "faintsSuffered")

    # Depth resets to 0 on a new map, and a new map is still progress.
    d_before, d_after = _depth(before), _depth(after)
    map_before = _run(before).get("map") or 0
    map_after = _run(after).get("map") or 0
    if map_after > map_before:
        r += 50
    elif d_after > d_before:
        r += 5 * (d_after - d_before)

    if done and won:
        r += 500
    return r


def survival(before, after, done=False, won=False) -> float:
    """Rewards staying alive, which is the densest signal available and a cautionary tale.

    Every step is worth something, so this should be easy to learn, and it is
    exactly the reward that can produce a bot which lingers safely without ever
    getting anywhere. The function is worth measuring for that reason.
    """
    r = 1.0
    r += -50 * _delta(before, after, "faintsSuffered")
    if done and not won:
        r -= 20
    if done and won:
        r += 500
    return r


def composite(before, after, done=False, won=False) -> float:
    """Rewards progression, with credit for fighting efficiently.

    Damage dealt and taken are counted by the engine every battle, so this adds a
    dense quality signal on top of progress, measuring how far you got and how
    cheaply you got there.
    """
    r = progress(before, after, done, won)
    r += 0.05 * _delta(before, after, "totalDamageDealt")
    r -= 0.05 * _delta(before, after, "totalDamageTaken")
    return r


AVAILABLE: dict[str, RewardFn] = {
    "game": game,
    "badges": badges,
    "progress": progress,
    "survival": survival,
    "composite": composite,
}


def get(name: str) -> RewardFn:
    if name not in AVAILABLE:
        raise KeyError(f"unknown reward '{name}' — available: {', '.join(sorted(AVAILABLE))}")
    return AVAILABLE[name]
