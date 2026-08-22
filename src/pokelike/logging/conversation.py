"""The whole conversation, as the model was actually given it.

One JSON object per decision in `<pass>-chat.jsonl`: the seed, the step, and the
messages exactly as they went out, system prompt included, with the assistant's
replies and every tool answer in between.

WHY IT IS RECORDED FROM OUTSIDE THE BOT. Every bot that talks to a model has a
`call_model(messages)`, and that is the one place the conversation is complete. So
this WRAPS that method rather than asking the bot to cooperate, which buys two
things that matter:

  - the frozen harnesses are covered. `llm-bench/<v>/harness/bot.py` builds its own
    messages and cannot be edited (a recorded result hashes it), so no callback
    could ever be added to it. Wrapping observes it without touching it, and the
    file's hash is exactly what it was.
  - anything that talks to a model is covered, including a bot somebody writes
    tomorrow with its own loop, as long as it goes through `call_model`.

Nothing is modified on the way through: the messages are passed to the real method
unchanged, and its answer is returned unchanged. A bot with no `call_model` (the
random bot, a policy, a search) is left alone and writes no file.

WHY ITS OWN FILE, and not a field in the decision trace. `model watch` re-reads the
whole trace on every refresh, a couple of times a second. A conversation is roughly
four thousand characters a decision on the shared prompt and thirteen thousand on
v5's, which is tens of megabytes over a fifty-seed pass: in the trace that would
turn the dashboard into a file scan. Beside it, the trace stays the small comparable
record it is and this grows as large as it likes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Conversations:
    """Writes every model exchange of a pass, one JSON object per decision.

    In: the path to write. Out: call `watch(bot)` to start recording, `close()`
    when the pass ends.
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

        In: the bot about to play. Out: True when it talks to a model at all.
        """
        call = getattr(bot, "call_model", None)
        if not callable(call):
            return False        # not a model-driven bot: nothing to record
        self._bot, self._original = bot, call

        def recording(messages: list[dict[str, Any]], *a: Any, **k: Any) -> Any:
            reply = self._original(messages, *a, **k)
            # Copied, because the caller keeps appending to the same list: without
            # the copy every round of a turn would end up holding the final state
            # of the conversation rather than what it actually sent.
            self._pending.append({"sent": [dict(m) for m in messages],
                                  "reply": reply})
            return reply

        bot.call_model = recording        # type: ignore[method-assign]
        return True

    def turn(self, seed: int, step: int) -> None:
        """Names the decision the next exchanges belong to.

        In: the seed and step about to be decided. Out: nothing.
        """
        self.seed, self.step = seed, step

    def flush(self) -> None:
        """Writes the exchanges of the decision just made, if there were any.

        In: nothing. Out: one line appended per decision.
        """
        if not self._pending:
            return
        if self.fh is None:
            self.fh = self.path.open("w", encoding="utf-8", buffering=1)
        rounds = self._pending
        self._pending = []
        # One line per DECISION, not per round: a turn can call several tools before
        # it plays, and those rounds are one conversation, not several.
        self.fh.write(json.dumps({"seed": self.seed, "step": self.step,
                                  "rounds": rounds}, ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Puts the bot's own method back and closes the file.

        In: nothing. Out: the bot is as it was.
        """
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
