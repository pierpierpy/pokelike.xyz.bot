"""llm-raw: the same prompt as llm-survivor, the whole state instead of a view.

Every other bot here reads `render.screen` (~831 characters, written for a person).
This one gets the state dict (~5900 characters of compact JSON) and works out what
matters by itself. Same prompt as llm-survivor, so the difference between the two
rows is the difference between reading a summary and reading the data.

Costs about 8x the tokens per turn (~1.8M per fifty-seed benchmark against ~275k).
Whether the extra data is worth the room it takes from reasoning is exactly what
running both answers.

The prompt is deliberately unchanged from llm-survivor. Tuning it for JSON would be
a fair thing to try and a different experiment: two variables moving at once tells
you nothing about either.

Credentials come from `.env` at the repository root.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class RawBot(LLMBot):
    name = "llm-raw"

    # state_view="json" sends the whole state dict every turn instead of the
    # rendered view. That is the one thing this bot changes from llm-survivor.
    config = LLMConfig(state_view="json", prompt=GAME_RULES + """
PLAY LIKE THIS
- Early on you have one Pokemon. If it faints you have lost. Widening the team is
  worth more than any experience you could gain.
- Never walk a Pokemon on low HP into a fight. Heal first if a pokecenter is
  reachable.
- Prefer a wild fight over a trainer when your team is thin: trainers bring more
  Pokemon and scale with the map.
- Type matchups decide battles. Check your team before choosing a fight.

Think briefly, then call `play`. Always call `play`.""")
