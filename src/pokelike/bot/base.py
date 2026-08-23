"""The interface every bot implements.

A bot picks an action given the state; nothing else is its job.

    class MyBot(Bot):
        def act(self, state):
            return 0   # index into state["actions"]

The index must stay within `len(state["actions"])`, or the move fails.

The `reset` and `finish` methods are optional hooks for bots that carry memory
across turns (an LLM's conversation, an RL agent's trajectory). Both have empty
default bodies, so ignore them if you don't need them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Bot(ABC):
    """This is the base for every bot. The `act` method is the only required one."""

    name = "bot"

    def __init__(self, seed: int = 0) -> None:
        """Every bot is built with a seed, whether or not the bot uses one.

        Subclasses may override this method freely to load weights or open a client.
        """
        self.seed = seed

    @abstractmethod
    def act(self, state: dict[str, Any]) -> int:
        """Return the index of the chosen action within `state["actions"]`.

        The `state` dict has these keys: `team`, `bag`, `map`, `run`, `actions`,
        `steps`, `screen`. See `core/render.py` for how to read the state.
        """

    def reset(self, seed: int) -> None:
        """Called before the first turn of each run."""

    def finish(self, state: dict[str, Any], score: dict[str, Any] | None) -> None:
        """Called once the run is over, with the final state and the score."""

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Swap two team slots before choosing, or return None to leave the order.

        Slot 0 leads the next battle. Reordering is free and does not consume
        the turn. This method is called once per turn, before `act`, only while
        `state["can_reorder"]` is true. Return `(a, b)` to swap those slots.
        The run loop applies the swap and re-reads the state before calling `act`.
        """
        return None

    def reason(self) -> str:
        """Return one line explaining why the last `act` chose what it chose.

        This hook is optional and used only by the detailed decision log. Return
        "" if there is nothing to add.
        """
        return ""

    def metadata(self) -> dict[str, Any]:
        """Return extra facts to record beside the score in the run registry and
        `result.json`.

        This returns an empty dict by default. Override to record what your bot
        varies (episode count, model name, fallback rate). Never put API tokens
        or endpoints here, because `result.json` is committed.
        """
        return {**self.add_metadata()}

    def add_metadata(self) -> dict[str, Any]:
        """Return your own facts, which are merged into `metadata()`.

        Return any dict; the merging into the base metadata is handled for you.
        """
        return {}

    def region_cleared(self, done: dict[str, Any]) -> str | None:
        """Return what the next region should open with when a campaign crosses one.

        This is called with the current region's memory still intact, so the bot
        can ask its model to summarise before the forgetting happens.
        """
        return None

    def region_opening(self, text: str) -> None:
        """Receive what the last region left for the bot, before the next one starts."""

    def reset_memory(self, keep: tuple[str, ...] = ()) -> None:
        """Forget the region just finished, keeping only what `keep` names."""

    def memory_text(self, include_scratch: bool = False) -> str:
        """Return the bot's memory as a single text string, or ""."""
        return ""

    def memory_messages(self, n: int | None = None) -> list[dict[str, Any]]:
        """Return the kept turns as message dicts, newest last, or []."""
        return []

    def artifacts(self) -> list:
        """Return what to archive alongside a standings result.

        Return a list of `pokelike.arena.leaderboard.Artifact` (weights, prompts,
        hyperparameters). Whatever is returned here is copied into the submission
        folder and hashed into the fingerprint.
        """
        return []
