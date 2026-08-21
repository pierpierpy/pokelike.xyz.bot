"""Do not die.

Faints are what ends runs, and a run that ends early scores nothing
whatever it did first. This prompt spends the whole run buying itself
more run.

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."              # whichever model you want to measure
    uv run pokelike bot run --bot llm-survivor --runs 3

The prompt below is the whole submission. Everything else — the tools, the loop,
how the state is rendered, what happens on a timeout — is in
`pokelike.bot.llm`, shared by every LLM bot so that a difference in results is a
difference between models and prompts rather than between harnesses.

`MODEL` is left unset, so this plays whatever `$MODEL_ID` names and the result
records which model that was. Pin it in your own bot if you want a leaderboard
row that means one specific model for good.
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
