"""llm-baseline: the rules, and nothing else.

The control. Told what the game is and left to work out how to play it, so every
other prompt can be read as a claim about what the model does not figure out on
its own.

Credentials come from `.env` at the repository root.

The prompt is the whole submission. The tools, the loop, the rendering and the
timeout policy are shared (`pokelike.bot.llm`), so a difference in results is a
difference between models and prompts, not between harnesses.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class BaselineBot(LLMBot):
    name = "llm-baseline"

    config = LLMConfig(prompt=GAME_RULES + """
Think briefly, then call `play` with your chosen index. Always call `play`.""")
