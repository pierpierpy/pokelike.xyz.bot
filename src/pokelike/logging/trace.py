"""Trace enrichment: adds context a bot knows to each logged decision.

Extracted from the model benchmark's `passes.py` closures so both the bot
competition and the model benchmark can feed a PassLog without duplicating the
logic that attaches tool calls and the map picture.

A non-LLM bot has no `tool_calls_made()` method, no notebook and no plan. The
helper handles that gracefully: it adds tool calls only when the bot provides
them, and draws the map only when the observation carries one.
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

    In: the raw decision entry, the bot instance, the last observation, and a
    one-element list holding the last drawn map (mutated as a closure would).
    Out: the enriched entry (a new dict when extras are added, or the original).

    `last_map` is a one-element list so it can be mutated across calls without
    a class or a nonlocal: the caller keeps `[""]` and passes it every time.
    """
    extra: dict[str, Any] = {}

    # Tool calls: only present on bots that keep track (the frozen harness bots).
    if hasattr(bot, "tool_calls_made") and callable(bot.tool_calls_made):
        called = bot.tool_calls_made()
        if called:
            extra["tools"] = called

    # The region, so a campaign's trace says WHERE each decision was taken: the map
    # number restarts at every boundary, and without this `map 1` means four things.
    # ALWAYS, including Kanto: a campaign starts there, and a live view that stays blank
    # until the first boundary is a view that says nothing for the whole first region.
    if obs and obs.get("region"):
        extra["region"] = obs["region"]

    # Map picture: drawn from the observation when it carries nodes.
    if obs and (obs.get("map") or {}).get("nodes"):
        from ..core import render

        picture = render.map_view(obs["map"])
        if picture and picture != last_map[0]:
            extra["map_view"] = picture
            last_map[0] = picture

    if extra:
        return {**entry, **extra}
    return entry
