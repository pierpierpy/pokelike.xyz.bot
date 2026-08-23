"""The whole conversation, as the model was actually given it.

One JSON object per decision in `<pass>-chat.jsonl`: the seed, the step, and the
messages exactly as they went out (system prompt included, with the assistant's
replies and every tool answer in between).

Recording works by wrapping `bot.call_model`: messages pass through unchanged and
the reply is returned unchanged, but both are captured. A bot with no `call_model`
(the random bot, a policy, a search) writes no file.

Conversations live in their own file rather than in the decision trace because
they are large (4-13 k characters per turn) and would make the trace too heavy
for `model watch` to refresh several times a second.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Conversations:
    """Writes every model exchange of a pass, one JSON object per decision.

    Call `watch(bot)` to start recording, then `close()` when the pass ends.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fh: Any = None
        self.seed: int | None = None
        self.step: int | None = None
        self._pending: list[dict[str, Any]] = []
        self._original: Any = None
        self._bot: Any = None

    def watch(self, bot: Any) -> bool:
        """Starts recording what this bot sends its model.

        Returns True when the bot talks to a model, False otherwise.
        """
        call = getattr(bot, "call_model", None)
        if not callable(call):
            return False        # not a model-driven bot: nothing to record
        self._bot, self._original = bot, call

        def recording(messages: list[dict[str, Any]], *a: Any, **k: Any) -> Any:
            reply = self._original(messages, *a, **k)
            # Copy messages: the caller keeps appending to the same list, so
            # without a copy every round would hold the final state.
            self._pending.append({"sent": [dict(m) for m in messages],
                                  "reply": reply})
            return reply

        bot.call_model = recording        # type: ignore[method-assign]
        return True

    def turn(self, seed: int, step: int) -> None:
        """Names the decision the next exchanges belong to.

        Sets the seed and step for the current turn.
        """
        self.seed, self.step = seed, step

    def flush(self) -> None:
        """Writes the exchanges of the current decision, if there were any."""
        if not self._pending:
            return
        if self.fh is None:
            self.fh = self.path.open("w", encoding="utf-8", buffering=1)
        rounds = self._pending
        self._pending = []
        # One line per decision, not per round: a turn can call several tools
        # before playing, and those rounds form one conversation.
        self.fh.write(json.dumps({"seed": self.seed, "step": self.step,
                                  "rounds": rounds}, ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Restores the bot's original method and closes the file."""
        self.flush()
        if self._bot is not None and self._original is not None:
            try:
                del self._bot.call_model      # remove the instance attribute
            except AttributeError:
                self._bot.call_model = self._original    # type: ignore[method-assign]
        if self.fh is not None and not self.fh.closed:
            self.fh.close()

    def __enter__(self) -> "Conversations":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
