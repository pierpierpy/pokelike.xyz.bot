"""Trace enrichment, adding tool calls and the map picture to each logged decision.

Both the bot arena and the model benchmark call `enrich_decision` to attach
context a bot knows to the decision entry. A non-LLM bot (one without a
`tool_calls_made` method) is handled gracefully and receives only the map picture
when available.
"""

from __future__ import annotations

from typing import Any


def enrich_decision(
    entry: dict[str, Any],
    bot: Any,
    obs: dict[str, Any] | None,
    last_map: list[str],
) -> dict[str, Any]:
    """Adds tool calls and the map picture to a decision entry.

    The `last_map` parameter is a one-element list mutated across calls so the
    caller can track state without a class. Pass `[""]` and reuse the list every
    time. The map is only included when it differs from the previous call.
    """
    extra: dict[str, Any] = {}

    # Tool calls are present only on bots that track them.
    if hasattr(bot, "tool_calls_made") and callable(bot.tool_calls_made):
        called = bot.tool_calls_made()
        if called:
            extra["tools"] = called

    # The region is included so a campaign's trace identifies where each decision was.
    if obs and obs.get("region"):
        extra["region"] = obs["region"]

    # The map picture is included only when the observation has nodes and the map changed.
    if obs and (obs.get("map") or {}).get("nodes"):
        from ..core import render

        picture = render.map_view(obs["map"])
        if picture and picture != last_map[0]:
            extra["map_view"] = picture
            last_map[0] = picture

    if extra:
        return {**entry, **extra}
    return entry
