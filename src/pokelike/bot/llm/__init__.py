"""The harness every LLM bot shares.

An LLM bot is a prompt and a model. Everything around them (how the state
becomes text, which tools exist, how many rounds of thinking are allowed, what
happens when a call fails) is machinery, and it lives here rather than in each
bot, for one reason: a benchmark of models has to hold the harness still.
Two bots with different loops are not two models being compared, they are two
harnesses, and the model is the smaller half of the difference.

So a bot built on this is short: a prompt in an `LLMConfig`.

    from pokelike.bot.llm import LLMBot, LLMConfig, GAME_RULES

    class SurvivorBot(LLMBot):
        name = "llm-survivor"
        config = LLMConfig(
            prompt=GAME_RULES + "Heal before it is urgent. Always call play().",
        )

Credentials never appear in a bot file. They come from the environment, always:

    export FW_ENDPOINT="https://..."     # base URL; /v1/chat/completions is added
    export FW_TOKEN="..."
    export MODEL_ID="..."                # unless the config pins `model` itself
    uv run pokelike bot run --bot llm-survivor --runs 3

This file is shared, which is the thing to be careful about. The whole point
of a bot being self-contained is that improving our code cannot silently change
what a past measurement meant. Code in here is the exception: it is shared on
purpose, so editing it does reach every LLM bot ever measured. `harness_version`
is how that stays honest: it is written into every result, and a result recorded
under an older harness is flagged in the standings instead of quietly being
compared against results from a newer one. Bump it whenever a change here
could move a decision.

Why `urllib` and not a client library: the package has two dependencies, and an
LLM bot should not add a third. One wire format, OpenAI-compatible, which nearly
every provider speaks (including Anthropic, through its compatibility endpoint).
A multi-provider abstraction would be more code to maintain and one more place
for two models to be asked subtly different questions.
"""

# Re-export every name that used to live at module level in the old single-file
# layout. Tests and bots import from `pokelike.bot.llm` and must keep working.

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
