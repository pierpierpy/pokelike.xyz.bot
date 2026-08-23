"""A bot that picks uniformly at random among the legal actions.

This is the baseline. It ignores the state entirely and dies within a few
dozen moves, and it is fully reproducible because the same seed always replays
the same run, since Python's random module is seeded once at construction.
"""

from __future__ import annotations

import random
from typing import Any

from pokelike.bot.base import Bot


class RandomBot(Bot):
    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def reset(self, seed: int) -> None:
        # Reseed from the run's seed so the choice sequence belongs to the run.
        self._rng = random.Random(seed)

    def act(self, state: dict[str, Any]) -> int:
        return self._rng.randrange(len(state["actions"]))

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Random team order, treating "leave it alone" as one of the options.

        A fair baseline must randomize every decision the game offers, including
        who leads the next battle.
        """
        team = state.get("team") or []
        if not state.get("can_reorder") or len(team) < 2:
            return None
        pick = self._rng.randrange(len(team))      # 0 means "leave it"
        return None if pick == 0 else (0, pick)
