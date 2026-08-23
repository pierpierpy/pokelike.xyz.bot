"""The harness every LLM bot shares.

A bot built on this is a prompt in an LLMConfig:

    from pokelike.bot.llm import LLMBot, LLMConfig, GAME_RULES

    class SurvivorBot(LLMBot):
        name = "llm-survivor"
        config = LLMConfig(
            prompt=GAME_RULES + "Heal before it is urgent. Always call play().",
        )

Credentials come from the environment (FW_ENDPOINT, FW_TOKEN, MODEL_ID) or from
the command line, never from a bot file.

This module is shared across all LLM bots, so editing it reaches every one.
Bump `harness_version` whenever a change here could move a decision.
"""

# Public API: tests and bots import from `pokelike.bot.llm`.

from .agent import HARNESS, LLMBot  # noqa: F401
from .config import (  # noqa: F401
    LLMBudgetError,
    LLMConfig,
    LLMConfigError,
    LLMError,
    StateView,
)
from .decorator import tool  # noqa: F401
from .fallback import _as_index, _parse_index, fallback_move_default  # noqa: F401
from .notebook import Notebook  # noqa: F401
from .tools import CLOSING, GAME_RULES, TOOLS, _STOCK_TOOL_NAMES, build_tools  # noqa: F401

__all__ = [
    "CLOSING",
    "GAME_RULES",
    "HARNESS",
    "LLMBot",
    "LLMBudgetError",
    "LLMConfig",
    "LLMConfigError",
    "LLMError",
    "Notebook",
    "StateView",
    "TOOLS",
    "_STOCK_TOOL_NAMES",
    "_as_index",
    "_parse_index",
    "build_tools",
    "fallback_move_default",
    "tool",
]
