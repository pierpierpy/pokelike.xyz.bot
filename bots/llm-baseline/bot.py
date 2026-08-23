"""The llm-baseline bot serves as the control.

The prompt explains the game and lets the model work out how to play on its own.
Every other prompt's additional guidance can then be measured against this baseline
to determine how much the extra instruction helps.

Credentials come from `.env` at the repository root.

The prompt is the whole submission. The tools, the loop, the rendering, and the
timeout policy are shared (`pokelike.bot.llm`), so a difference in results is a
difference between models and prompts, not between harnesses.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class BaselineBot(LLMBot):
    name = "llm-baseline"

    config = LLMConfig(prompt=GAME_RULES + """
Think briefly, then call `play` with your chosen index. Always call `play`.""")
