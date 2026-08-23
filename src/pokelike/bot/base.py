"""The interface every bot implements.

A bot picks an action given the state; nothing else is its job.

    class MyBot(Bot):
        def act(self, state):
            return 0   # index into state["actions"]

The index must stay within `len(state["actions"])`, or the move fails.

`reset` and `finish` are optional hooks for bots that carry memory across turns
(an LLM's conversation, an RL agent's trajectory). Both have empty default
bodies, so ignore them if you don't need them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Bot(ABC):
    """Base for every bot. `act` is the only required method."""

    name = "bot"

    def __init__(self, seed: int = 0) -> None:
        """Every bot is built with a seed, whether or not it uses one.

        Override freely to load weights or open a client.
        """
        self.seed = seed

    @abstractmethod
    def act(self, state: dict[str, Any]) -> int:
        """Index of the chosen action within `state["actions"]`.

        `state` is the full dict: `team`, `bag`, `map`, `run`, `actions`,
        `steps`, `screen`. See `core/render.py` for how to read it.
        """

    def reset(self, seed: int) -> None:
        """Called before the first turn of each run."""

    def finish(self, state: dict[str, Any], score: dict[str, Any] | None) -> None:
        """Called once the run is over, with the final state and the score."""

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Optional: swap two team slots before choosing, or None to leave it.

        Slot 0 leads the next battle. Reordering is free: it does not consume
        the turn. Called once per turn, before `act`, only while
        `state["can_reorder"]` is true. Return `(a, b)` to swap those slots.
        The run loop applies the swap and re-reads the state before calling `act`.
        """
        return None

    def reason(self) -> str:
        """One line explaining why the last `act` chose what it chose.

        Optional, used only by the detailed decision log. Return "" if there
        is nothing to add.
        """
        return ""

    def metadata(self) -> dict[str, Any]:
        """Extra facts recorded beside the score in the run registry and
        `result.json`.

        Empty by default. Override to record what your bot varies (episode count,
        model name, fallback rate). Never put API tokens or endpoints here,
        because `result.json` is committed.
        """
        return {**self.add_metadata()}

    def add_metadata(self) -> dict[str, Any]:
        """Your own facts, merged into `metadata()`.

        Return any dict; the merging into the base metadata is handled for you.
        """
        return {}

    def region_cleared(self, done: dict[str, Any]) -> str | None:
        """What the next region should open with, when a campaign crosses one.

        Called with the current region's memory still intact, so the bot can
        ask its model to summarise before the forgetting happens.
        """
        return None

    def region_opening(self, text: str) -> None:
        """Hands the bot what the last region left it, before the next one starts."""

    def reset_memory(self, keep: tuple[str, ...] = ()) -> None:
        """Forgets the region just finished, keeping only what `keep` names."""

    def memory_text(self, include_scratch: bool = False) -> str:
        """The bot's memory as a single text string, or ""."""
        return ""

    def memory_messages(self, n: int | None = None) -> list[dict[str, Any]]:
        """The kept turns as message dicts, newest last, or []."""
        return []

    def artifacts(self) -> list:
        """What to archive alongside a leaderboard result.

        Return a list of `pokelike.arena.leaderboard.Artifact` (weights, prompts,
        hyperparameters). Whatever is returned here is copied into the submission
        folder and hashed into the fingerprint.
        """
        return []
