"""A bot that picks uniformly at random among the legal actions.

It looks at nothing: not HP, not types, not what lies ahead on the map. It is
the baseline — it dies within a couple of dozen moves without ever clearing the
first map, so any real player has to beat it.

It is reproducible: the same seed replays the same run.
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
        # Reseed from the run's seed so the sequence of choices belongs to the
        # run, not to how many runs came before it.
        self._rng = random.Random(seed)

    def act(self, state: dict[str, Any]) -> int:
        return self._rng.randrange(len(state["actions"]))

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Also random about who leads, which is what makes it a fair baseline.

        Team order is a decision the game offers and this bot is meant to take
        every decision uniformly. Leaving `rearrange` at its default would have
        made it random about moves but FIXED about order — a baseline that is
        secretly following one policy, and an unfair yardstick for any bot that
        does think about the order.

        "Leave it alone" is one of the options rather than the fallback, so it
        gets the same weight as each swap and doing nothing is not privileged.
        """
        team = state.get("team") or []
        if not state.get("can_reorder") or len(team) < 2:
            return None
        pick = self._rng.randrange(len(team))      # 0 means: leave it
        return None if pick == 0 else (0, pick)
