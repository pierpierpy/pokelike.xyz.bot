"""Metadata and artifact generation for LLM bot submissions.

What gets recorded alongside a benchmark result: the model reference, the prompt,
the token counts, and whether the bot answered the same question as the others.
"""

from __future__ import annotations

from typing import Any

from .tools import _STOCK_TOOL_NAMES


def build_metadata(
    *,
    model: str,
    harness_version: int,
    bot_class_name: str,
    calls: int,
    turns: int,
    tokens_used: int,
    tokens_in: int,
    tokens_out: int,
    retry_count: int,
    fallbacks: int,
    temperature: float,
    tool_names: list[str],
    state_view_label: str,
) -> dict[str, Any]:
    """Builds the metadata dict written into the run registry and result files.

    In: all the counters and config from the bot instance. Out: a dict ready for
    JSON serialization.
    """
    # `fallback_rate` is the honest column of an LLM benchmark. Every fallback
    # is a turn the model did not decide, played by the backup heuristic under
    # the model's name, so a row with a high one is measuring our heuristic,
    # not the model.
    return {
        "model": model,
        "harness": harness_version,
        "bot": bot_class_name,
        "calls": calls,
        "turns": turns,
        "tokens": tokens_used,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "retries": retry_count,
        "fallbacks": fallbacks,
        "fallback_rate": round(fallbacks / turns, 3) if turns else 0.0,
        "temperature": temperature,
        "stock_tools": tool_names == _STOCK_TOOL_NAMES,
        "state_view": state_view_label,
        "reproducible": False,
    }


def build_artifacts(
    *,
    bot_class_name: str,
    prompt: str,
    model: str,
    model_pinned: bool,
    harness_version: int,
    temperature: float,
    max_tokens: int,
    max_rounds: int,
    memory: int,
    token_budget: int,
    tool_names: list[str],
    state_view_label: str,
) -> list:
    """Builds the list of Artifact objects a submission carries.

    In: the bot's configuration values. Out: a list of Artifact instances
    (prompt and model-ref).
    """
    # The prompt and the model reference, never the key. An LLM result cannot
    # be reproduced exactly (providers change models behind a fixed name and
    # sampling is stochastic) so the least we can do is record precisely what
    # was asked of which model, under which harness.
    from pokelike.arena.leaderboard import Artifact

    return [
        Artifact(
            name="prompt.md",
            kind="prompt",
            description=f"system prompt, {bot_class_name}",
            text=prompt,
        ),
        Artifact(
            name="model.json",
            kind="model-ref",
            description="which model answered, and how it was asked",
            data={
                "model": model,
                "pinned": model_pinned,
                "harness": harness_version,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "max_rounds": max_rounds,
                "memory": memory,
                "token_budget": token_budget,
                "tools": tool_names,
                "stock_tools": tool_names == _STOCK_TOOL_NAMES,
                "state_view": state_view_label,
                "reproducible": False,
                "why_not": (
                    "providers change models behind a fixed name and sampling is "
                    "stochastic; rerunning this will not give identical results"
                ),
            },
        ),
    ]
