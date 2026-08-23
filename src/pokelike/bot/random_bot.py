"""A bot that picks uniformly at random among the legal actions.

It looks at nothing: not HP, not types, not the map. It is the baseline, and it
is reproducible (the same seed replays the same run).
"""

from __future__ import annotations

import random
from typing import Any

from .base import Bot


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
        """Random about who leads, so the baseline covers every decision uniformly.

        "Leave it alone" is one of the outcomes (pick == 0), given equal weight.
        """
        team = state.get("team") or []
        if not state.get("can_reorder") or len(team) < 2:
            return None
        pick = self._rng.randrange(len(team))      # 0 means: leave it
        return None if pick == 0 else (0, pick)
