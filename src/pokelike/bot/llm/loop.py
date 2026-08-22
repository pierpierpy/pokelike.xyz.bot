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
) -> tuple[int | None, str, int | None]:
    """Executes one turn of the agentic loop until play() is called.

    In: the state, config flags, and callback functions for model calls, tool
    answers, and index parsing. Out: (action index or None, reason, lead or None).
    Raises LLMError if the model never calls play() within max_rounds.
    """
    lead: int | None = None
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for _ in range(max_rounds):
        msg = call_model_fn(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            # No tool: maybe it wrote the index out in prose.
            index = parse_index_fn(msg.get("content") or "", len(state["actions"]))
            if index is not None:
                return index, "(read from prose)", lead
            raise LLMError("the model called no tool")

        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": calls,
        })

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
                return as_index_fn(args.get("index")), str(args.get("why", "")), lead

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
                messages.append({
                    "role": "tool", "tool_call_id": c["id"], "content": reply,
                })
                continue

            messages.append({
                "role": "tool",
                "tool_call_id": c["id"],
                "content": answer_tool_fn(name, args, state),
            })

    raise LLMError(f"no call to play() within {max_rounds} rounds")
