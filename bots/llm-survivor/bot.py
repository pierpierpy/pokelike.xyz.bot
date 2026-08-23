"""llm-survivor: do not die.

Faints are what ends runs, and a run that ends early scores nothing whatever it did
first. This prompt spends the whole run buying itself more run.

Credentials come from `.env` at the repository root.

The prompt is the whole submission. The tools, the loop, the rendering, and the
timeout policy are shared (`pokelike.bot.llm`), so a difference in results is a
difference between models and prompts, not between harnesses.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class SurvivorBot(LLMBot):
    name = "llm-survivor"

    config = LLMConfig(prompt=GAME_RULES + """
PLAY LIKE THIS
- Early on you have one Pokemon. If it faints you have lost. Widening the team is
  worth more than any experience you could gain.
- Never walk a Pokemon on low HP into a fight. Heal first if a pokecenter is
  reachable.
- Prefer a wild fight over a trainer when your team is thin: trainers bring more
  Pokemon and scale with the map.
- Type matchups decide battles. Check your team before choosing a fight.

Think briefly, then call `play`. Always call `play`.""")
