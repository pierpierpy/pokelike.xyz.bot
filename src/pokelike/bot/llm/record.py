"""This module handles metadata and artifact generation for LLM bot submissions."""

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
    reasoning_effort: str | None,
    tool_names: list[str],
    state_view_label: str,
) -> dict[str, Any]:
    """Builds the metadata dict written into the run registry and result files."""
    # The fallback_rate field is the fraction of turns decided by the backup
    # heuristic.
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
        "reasoning_effort": reasoning_effort,
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
    reasoning_effort: str | None,
    max_tokens: int,
    max_rounds: int,
    memory: int,
    token_budget: int,
    tool_names: list[str],
    state_view_label: str,
) -> list:
    """Builds the list of Artifact objects a submission carries."""
    # The artifacts record the prompt and model reference, never the key.
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
                "reasoning_effort": reasoning_effort,
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
