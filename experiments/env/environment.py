"""This module provides an RL-shaped view of the game.

The `pokelike.Game` class speaks in dicts and action indices. An RL algorithm wants
(state, actions, reward, done) with hashable keys. This is the adapter, and it
is deliberately the only place where the two vocabularies meet.

The interface is the usual one:

    env = TrainingEnv()
    s, actions = env.reset(seed=1)
    s2, actions2, r, done = env.step("node:catch")

Actions are passed by key. The `TrainingEnv` resolves the key back to the right
index for that particular turn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pokelike.assets import AssetServer
from pokelike.core.game import Game

from .encoding import action_key, state_key
from .rewards import get as get_reward

SITE = Path(__file__).resolve().parents[2] / "site"


class TrainingEnv:
    """Wraps one live game instance for learning.

    Starting Chromium costs about a second, so the browser is opened once and
    every episode reuses it. The `reset` method starts a new run inside the same
    browser.
    """

    def __init__(self, port: int = 8600, max_steps: int = 300,
                 reward: str = "progress") -> None:
        if not (SITE / "index.html").is_file():
            raise RuntimeError(
                f"offline copy missing in {SITE}\nrun it once with: pokelike setup"
            )
        self.server = AssetServer(SITE, port=port)
        self.server.start()
        self.game = Game(url=self.server.url)
        self.game.open()
        self.max_steps = max_steps
        self.reward_name = reward
        self.reward_fn = get_reward(reward)
        self._obs: dict[str, Any] | None = None
        self._prev: dict[str, Any] | None = None

    # ------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self.game.close()
        self.server.stop()

    def __enter__(self) -> "TrainingEnv":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ----------------------------------------------------------------- gym-ish

    def reset(self, seed: int) -> tuple[tuple, list[str]]:
        self._obs = self.game.reset(seed=seed)
        self._prev = None
        return state_key(self._obs), self.legal_actions()

    def legal_actions(self) -> list[str]:
        """Returns the action keys available right now.

        Duplicates are possible in principle when two slots map to one key; this
        method keeps the first, since the algorithm can only pick a key anyway.
        """
        seen: dict[str, int] = {}
        for i, a in enumerate(self._obs.get("actions") or []):
            seen.setdefault(action_key(a), i)
        return list(seen)

    def step(self, key: str) -> tuple[tuple, list[str], float, bool]:
        """Takes the action with that key. Returns (state, actions, reward, done)."""
        index = self._index_of(key)
        if index is None:
            raise KeyError(f"action '{key}' is not legal here: {self.legal_actions()}")

        before = self._obs
        self._prev = before
        self._obs = self.game.step(index)

        done = bool(self._obs.get("done")) or self.game.steps >= self.max_steps
        won = self._obs.get("screen") == "win-screen"
        # At game over the engine wipes `state`, so the badge count and the team
        # are gone from the final observation. Reward against the last live
        # snapshot instead, or the last transition of every run would look like a
        # catastrophic loss of everything.
        after = self._obs if self._obs.get("run") else (self.game.last_alive or before)
        reward = self.reward_fn(before, after, done, won)

        return state_key(self._obs), self.legal_actions(), reward, done

    # ---------------------------------------------------------------- helpers

    def _index_of(self, key: str) -> int | None:
        for i, a in enumerate(self._obs.get("actions") or []):
            if action_key(a) == key:
                return i
        return None

    def score(self) -> dict[str, Any] | None:
        """Returns the game's own end-of-run score, used for reporting only."""
        return self.game.score()

    @property
    def steps(self) -> int:
        return self.game.steps

    @property
    def observation(self) -> dict[str, Any] | None:
        """Returns the raw observation, for policies that want more than the compressed key."""
        return self._obs
