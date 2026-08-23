"""This module implements the multi-round agentic loop that drives one turn of thinking.

The loop calls the model up to `max_rounds` times, dispatches tool calls, and
returns when `play()` is called or raises when the budget is exhausted.
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

    Returns (action index or None, reason, lead or None, this_turn exchange).
    Raises LLMError if the model never calls play() within max_rounds.
    """
    lead: int | None = None
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *(history or []),
        {"role": "user", "content": user_message},
    ]
    # What this turn adds to the scratchpad, separate from the full messages list.
    this_turn: list[dict[str, Any]] = [messages[-1]]

    for _ in range(max_rounds):
        msg = call_model_fn(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            # The model called no tool, so it may have written the index in prose.
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
            # Recording happens before dispatch because play, set_lead, and
            # unknown names all return or continue without reaching answer_tool.
            if record_call_fn is not None:
                record_call_fn(name, args)

            if name == "play":
                # Every tool_call in the assistant message needs a tool response,
                # including this one; fill stubs for any remaining calls.
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
                # The run loop performs the swap; here we just record the intent.
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
    """Raised when rounds are exhausted without a play() call.

    The exception carries the exchange so the caller can add it to the scratchpad.
    """

    def __init__(self, msg: str, this_turn: list[dict[str, Any]]) -> None:
        super().__init__(msg)
        self.this_turn = this_turn
