"""The interface every bot implements.

A bot is one thing only: something that, given the state, says **which action to
take**. Everything else — starting the browser, applying the move, computing the
score — is none of its business.

    class MyBot(Bot):
        def choose(self, state):
            return 0          # index into state["actions"]

The index is the position in `state["actions"]`, the same numbered list you see
when playing from the CLI. Returning an index out of range makes the move fail,
so a bot must always stay within `len(state["actions"])`.

The two hooks `on_start` and `on_end` are for bots that need memory across
turns:

- an **LLM** resets its conversation in `on_start` and closes it in `on_end`;
- an **RL** algorithm accumulates the trajectory and receives the final score in
  `on_end`, which is its reward signal;
- a **scripted** bot resets its move counter in `on_start`.

Bots that need neither can ignore them: both already have empty bodies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Bot(ABC):
    """Base for every bot. `choose` is the only required method."""

    name = "bot"

    def __init__(self, seed: int = 0) -> None:
        """Every bot is built with a seed, whether or not it uses one.

        Defined here so that writing a bot with no `__init__` at all — which is
        the normal case for anything that does not need randomness — still works
        when something builds it by name. Override it freely; a bot that needs
        to load weights or open a client does its work here.
        """
        self.seed = seed

    @abstractmethod
    def choose(self, state: dict[str, Any]) -> int:
        """Index of the chosen action within `state["actions"]`.

        `state` is the full dict: `team`, `bag`, `map`, `run`, `actions`,
        `steps`, `screen`. See `core/render.py` for how to read it.
        """

    def on_start(self, seed: int) -> None:
        """Called before the first turn of each run."""

    def on_end(self, state: dict[str, Any], score: dict[str, Any] | None) -> None:
        """Called once the run is over, with the final state and the score."""

    def rearrange(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Optional: swap two team slots before choosing, or None to leave it.

        Slot 0 is the Pokemon that leads the next battle, so the order is a real
        decision. It is kept apart from `choose` because it is a FREE action: it
        does not consume the turn, and folding it into `state["actions"]` would
        add fifteen swap pairs to a full team's option list at every map node,
        burying the moves that actually advance the run.

        Called once per turn, before `choose`, and only while
        `state["can_reorder"]` is true. Return `(a, b)` to swap those slots.
        The run loop applies it and re-reads the state, so the `state` passed to
        `choose` already reflects the swap.

        Ignoring this is exactly what every bot did before it existed, so a bot
        that does not implement it plays as it always has.
        """
        return None

    def explain(self) -> str:
        """One line on why the last `choose` went the way it did.

        Optional, and only used by the detailed log. The shared run loop already
        records what every bot has in common — the screen, the options, which one
        was taken — so this is for the part only the bot knows: an LLM's stated
        reason, a table's learned values, a heuristic's rule.

        Returning "" means "nothing to add", which is honest for a bot that picks
        at random.
        """
        return ""

    def artifacts(self) -> list:
        """What to archive alongside a leaderboard result.

        Return a list of `pokelike.arena.leaderboard.Artifact`: weights, prompts, the
        model you called, the hyperparameters you trained with. A bot made of
        plain rules has nothing to declare and can ignore this.

        Whatever is returned here is copied into the submission folder and
        hashed, so the result can never be separated from what produced it.
        """
        return []
