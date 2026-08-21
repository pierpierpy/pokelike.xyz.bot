"""Configuration and error types for the LLM harness.

LLMConfig is the single validated place for every knob an LLM bot can turn.
The three error classes separate what should stop the run from what should fall
back: an auth failure kills it, a timeout falls back, and a spent budget kills it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMError(RuntimeError):
    """Something went wrong on one call. Recoverable: fall back and play on."""


class LLMConfigError(LLMError):
    """The setup is wrong and every call will fail the same way.

    A bad token, a model name the endpoint does not serve, a URL that is not an
    OpenAI-compatible API. Falling back on these would play a whole run on the
    backup heuristic and report it as an LLM result, which, in a benchmark, puts
    an entry on the leaderboard labelled `llm` that no model ever played.
    So these stop the run instead.
    """


class LLMBudgetError(LLMError):
    """The run asked for more tokens than the bot allowed itself.

    Only raised when a config sets `token_budget`. A model that thinks ten times
    longer than the others is not straightforwardly better than them, and over
    fifty runs the difference is money, so a bot may declare a ceiling and be
    held to it rather than discovering the bill afterwards.
    """


# --------------------------------------------------------------------- config

StateView = Literal["screen", "json", "both"] | list[str]


class LLMConfig(BaseModel):
    """Every knob an LLM bot can turn, in one validated place.

    A bot sets the ones it cares about and inherits the rest:

        config = LLMConfig(prompt=GAME_RULES + "...", temperature=0.3)

    `extra="forbid"` means a typo in a field name is caught the moment the bot is
    built, not fifty runs later. Credentials are deliberately NOT here: the
    endpoint and token come from the environment or the command line, because
    this object is fingerprinted and written into `result.json`.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str = ""                            # filled by __init__.py after GAME_RULES exists
    model: str | None = None                    # pin an id, or None to take $MODEL_ID
    temperature: float = 0.6
    max_tokens: int = 1500
    max_rounds: int = 4                          # tool rounds before the turn is given up
    memory: int = 6                              # past turns replayed; -1 = keep all
    token_budget: int = 0                        # per-run cap, 0 = none
    retries: int = 4                             # attempts on a transient HTTP failure
    extra_tools: list[dict[str, Any]] = Field(default_factory=list)
    state_view: StateView = "screen"             # what the model reads each turn
