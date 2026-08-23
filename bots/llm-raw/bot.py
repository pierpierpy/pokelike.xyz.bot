"""The llm-raw bot uses the same prompt as llm-survivor but sends the whole state
dict instead of a rendered view.

Every other bot here reads `render.screen` (about 831 characters, written for a
person). This bot receives the state dict (about 5900 characters of compact JSON)
and works out what matters by itself. The prompt is the same as llm-survivor, so
the difference between the two rows isolates the effect of reading a summary
versus reading the data.

This bot costs about 8x the tokens per turn, roughly 1.8M per fifty-seed
benchmark versus about 275k. Running both answers whether the extra data is
worth the room it takes from reasoning.

The prompt is deliberately unchanged from llm-survivor. Tuning the prompt for JSON
would be a fair thing to try and a different experiment, because two variables
moving at once tells you nothing about either.

Credentials come from `.env` at the repository root.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class RawBot(LLMBot):
    name = "llm-raw"

    # state_view="json" sends the whole state dict every turn instead of the
    # rendered view. That setting is the one thing this bot changes from llm-survivor.
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
