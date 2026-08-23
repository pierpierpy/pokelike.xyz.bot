"""llm-analyst: look before you leap.

This bot says nothing about how to play, only about what to read first. It is the
cheapest test of whether models lose runs by choosing badly or by choosing without
looking. It costs the most tokens per turn because every turn spends tool rounds
before committing.

Credentials come from `.env` at the repository root.

The prompt is the whole submission. The tools, the loop, the rendering, and the
timeout policy are shared (`pokelike.bot.llm`), so a difference in results is a
difference between models and prompts, not between harnesses.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class AnalystBot(LLMBot):
    name = "llm-analyst"

    config = LLMConfig(prompt=GAME_RULES + """
HOW TO DECIDE
Before choosing, gather what you need:
1. Call `team_details` if any HP or type matchup could matter here.
2. Call `what_lies_ahead` whenever you are on the map. What a node leads to
   matters as much as the node itself, because the others close forever.
Only then call `play`, naming in one sentence the option you rejected and why.

Always finish with `play`.""")
