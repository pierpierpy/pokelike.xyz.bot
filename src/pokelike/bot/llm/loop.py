"""The multi-round agentic loop that drives one turn of thinking.

A single turn: build the initial messages, call the model up to `max_rounds`
times, dispatch tool calls, and return when `play()` is called or raise when the
budget is exhausted. Everything stateful (counters, journal) stays on the bot;
this module is the pure conversation logic.
"""

from __future__ import annotations

import json
from typing import Any

from .config import LLMError


def run_turn(
    *,
    state: dict[str, Any],
    allow_lead: bool,
    system_prompt: str,
    user_message: str,
    max_rounds: int,
    call_model_fn: Any,
    answer_tool_fn: Any,
    record_call_fn: Any = None,
    parse_index_fn: Any,
    as_index_fn: Any,
    history: list[dict[str, Any]] | None = None,
) -> tuple[int | None, str, int | None, list[dict[str, Any]]]:
    """Executes one turn of the agentic loop until play() is called.

    In: the state, config flags, callback functions for model calls, tool
    answers, and index parsing, and an optional history of previous exchanges.
    Out: (action index or None, reason, lead or None, this_turn exchange).
    Raises LLMError if the model never calls play() within max_rounds.
    """
    lead: int | None = None
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *(history or []),
        {"role": "user", "content": user_message},
    ]
    # What this turn adds to the scratchpad, kept apart from `messages` so the
    # system prompt and the older turns are not copied into it again.
    this_turn: list[dict[str, Any]] = [messages[-1]]

    for _ in range(max_rounds):
        msg = call_model_fn(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            # No tool: maybe it wrote the index out in prose.
            index = parse_index_fn(msg.get("content") or "", len(state["actions"]))
            if index is not None:
                return index, "(read from prose)", lead, this_turn
            raise LLMError("the model called no tool")

        spoke = {
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": calls,
        }
        messages.append(spoke)
        this_turn.append(spoke)

        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            # Recorded HERE, before the dispatch, because `play`, `set_lead` and a
            # name the model invented all return or continue without reaching
            # `answer_tool`, and those are three of the things worth knowing about a
            # turn. Only the arguments that decide something are kept: a read-only
            # tool takes none, and its answer is reconstructible from the state,
            # which the trace already holds.
            if record_call_fn is not None:
                record_call_fn(name, args)

            if name == "play":
                # The turn ends. Every call in the assistant message must have a
                # tool answer, this one included: an assistant message with
                # `tool_calls` followed by nothing is a malformed request under
                # every provider, and would break the scratchpad on the next turn.
                answered = {m.get("tool_call_id") for m in this_turn
                            if m.get("role") == "tool"}
                for other in calls:
                    if other["id"] in answered:
                        continue
                    this_turn.append({
                        "role": "tool",
                        "tool_call_id": other["id"],
                        "content": (
                            f"played index {args.get('index')}."
                            if other is c else
                            "not run: the turn ended at play()."
                        ),
                    })
                return (
                    as_index_fn(args.get("index")),
                    str(args.get("why", "")),
                    lead,
                    this_turn,
                )

            if name == "set_lead":
                # Recorded, not applied here: the bot has no handle on the
                # game, and the run loop is what performs the swap. Kept even
                # when not allowed, so the model gets told why rather than
                # silently ignored.
                want = args.get("index")
                if allow_lead and isinstance(want, int):
                    lead = want
                    reply = f"ok, slot {want} will lead. Now call play()."
                else:
                    reply = ("not available on this screen: the options here are "
                             "your team, so reordering would change what an index "
                             "means. Call play().")
                answer = {"role": "tool", "tool_call_id": c["id"], "content": reply}
                messages.append(answer)
                this_turn.append(answer)
                continue

            answer = {
                "role": "tool",
                "tool_call_id": c["id"],
                "content": answer_tool_fn(name, args, state),
            }
            messages.append(answer)
            this_turn.append(answer)

    raise _LoopExhausted(f"no call to play() within {max_rounds} rounds", this_turn)


class _LoopExhausted(LLMError):
    """Rounds exhausted without a play() call. Carries the exchange for the scratchpad."""

    def __init__(self, msg: str, this_turn: list[dict[str, Any]]) -> None:
        super().__init__(msg)
        self.this_turn = this_turn
