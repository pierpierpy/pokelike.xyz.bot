"""This module provides state and action encoding, plus the step reward.

This is where most of the work in tabular RL actually lives. In a grid world the
state is an integer, so you index a dense table with it. Here the raw
observation is a dict holding a team, a bag and a graph, and there are
astronomically many of them. A table over raw states would never see the same
state twice and would learn nothing.

So we compress. Three decisions matter more than the algorithm sitting on top.


The state key
-------------
The key includes only features that plausibly change what the best move is. Every
extra feature multiplies the state space, and a state visited twice in a thousand
runs teaches you nothing. This is function approximation by hand, the crudest
kind, which is state aggregation (Sutton & Barto, section 9.3).


The action key
--------------
Actions are not stable by position. Index 2 means "battle" on one turn and
"catch" on the next, so learning Q(s, 2) would be learning noise. We key actions
by what they are, and Q(s, "node:catch") then accumulates across every turn
where catching was an option.

The table is a dict rather than a torch tensor for the same reason. In a grid
world the action set is fixed (up/down/left/right) and states are 0..N-1, so a
dense `Q[num_states, num_actions]` fits exactly. Here both dimensions are sparse
and string-keyed, and most (state, action) pairs never occur, so a dict is the
same idea with the zeros left out.


The reward
----------
We use the game's own scoring weights, applied per step instead of once at the
end. Optimising the same numbers the standings use avoids the classic trap of
training a bot that is great at a proxy nobody cares about.
"""

from __future__ import annotations

from typing import Any

# This measures how full the worst-off team member is, in four buckets. Finer
# buckets would split experience across cells that behave identically.
HP_THRESHOLDS = ((0.25, 0), (0.5, 1), (0.8, 2))


def hp_bucket(team: list[dict]) -> int:
    """Returns 0 when someone is nearly dead and 3 when everyone is healthy."""
    if not team:
        return 0
    alive = [p["hp"] / p["max_hp"] for p in team if p["max_hp"]]
    if not alive:
        return 0
    worst = min(alive)
    for threshold, bucket in HP_THRESHOLDS:
        if worst < threshold:
            return bucket
    return 3


def depth_bucket(state: dict[str, Any]) -> int:
    """Returns how far down the current map the player is, in three bands.

    The boss sits at the bottom, so depth changes what a good move looks like.
    Catching is worth more early, and healing is worth more just before the boss.
    """
    m = state.get("map")
    if not m or not m.get("current"):
        return 0
    layers = [n["layer"] for n in m["nodes"]]
    current = next((n["layer"] for n in m["nodes"] if n["id"] == m["current"]), 0)
    deepest = max(layers) if layers else 1
    frac = current / deepest if deepest else 0.0
    return 0 if frac < 0.34 else (1 if frac < 0.67 else 2)


def action_key(a: dict[str, Any]) -> str:
    """Returns what an action is, in a form that is stable across turns.

    Map moves are keyed by node type. Everything else (catch offers, item
    offers, equip modals) is keyed by screen plus slot, because there the
    options are homogeneous (three Pokemon to catch, three items to take) and
    what distinguishes them is which slot you take.
    """
    if a.get("kind") == "node":
        return f"node:{a['node']}"
    label = (a.get("label") or "").strip().lower()
    # A few buttons mean the same thing wherever they show up.
    for word, key in (("skip", "skip"), ("cancel", "cancel"),
                      ("keep in bag", "bag"), ("equip", "equip")):
        if word in label:
            return f"btn:{key}"
    return f"{a.get('layer', 'x')}:slot{a.get('idx', 0)}"


# Bumped whenever `state_key` changes. A saved table is keyed by encoded states,
# so an old table under a new encoding is meaningless.
ENCODING_VERSION = 2


def state_key(state: dict[str, Any]) -> tuple:
    """The compressed state. Keep it small because every field multiplies the table.

    Version 2 dropped the tuple of offered actions, which version 1 included on
    the theory that a cell should not mix turns offering different options. That
    theory was wrong, and the numbers said so. In 90 episodes there were 563 states
    holding 686 state-action pairs, about 1.2 actions per state. The agent almost
    never got to compare two moves in the same situation, which is the one thing
    a Q-table is for.

    Removing the offered-action tuple collapses those 563 states to 244 and lets
    Q(s, "node:catch") accumulate across every map turn that offered a catch,
    instead of splitting the evidence across every distinct menu it appeared in.
    The menu information is still preserved implicitly, because Q is keyed by
    action and a value only ever exists for actions that were actually offered.
    """
    run = state.get("run") or {}
    team = state.get("team") or []
    return (
        state.get("screen"),
        min(len(team), 6),
        hp_bucket(team),
        min(run.get("map") or 0, 8),
        depth_bucket(state),
        min(run.get("badges") or 0, 8),
    )


# --------------------------------------------------------------------- reward

# The game's own scoring weights. See the score formula in the README.
#   +500 completed, +5 per KO, -10 per faint, +50 per map, +20 per shiny/legendary
# The time bonus is dropped because the frozen clock pins it and it carries no
# information. The shiny/legendary terms are also dropped because they are read
# off the final team rather than counted per step.
WEIGHTS = {
    "enemiesKO": 5,
    "faintsSuffered": -10,
    "mapsCleared": 50,
}
WIN_BONUS = 500


def step_reward(before: dict[str, Any] | None, after: dict[str, Any] | None,
                done: bool = False, won: bool = False) -> float:
    """Computes the reward for one transition from the deltas of the engine's own counters.

    Those counters live in `state["stats"]` and the game updates them after each
    battle, so the reward reflects the engine's actual accounting.
    """
    r = 0.0
    if before and after:
        for field, weight in WEIGHTS.items():
            r += weight * ((after.get(field) or 0) - (before.get(field) or 0))
    if done and won:
        r += WIN_BONUS
    return r
