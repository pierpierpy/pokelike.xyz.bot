"""llm-raw: the same prompt as llm-survivor, and the whole state instead of a view.

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."
    uv run pokelike bot run --bot llm-raw --runs 3 -d

THE EXPERIMENT
Every other bot here reads `render.screen`, which is written for a person: HP as
a bar, the map as a picture. It is 631 characters and it leaves real things out
-- the engine's type/item table, which node connects to which, raw base stats --
because it shows what someone would look at rather than everything that is true.

This one gets the state dict, 5144 characters of compact JSON, and works out what
matters by itself. Same prompt as `llm-survivor`, so the difference between the
two rows is the difference between reading a summary and reading the data.

Both figures are the first map turn of seed 10000, the state every number in
`bots/llm-example/README.md` is taken at, so the two pages can be compared.

WHAT IT COSTS
About 8x the tokens per turn, which is roughly 1.8M per fifty-seed benchmark
against 275k. And the cost is not only money: a map the turn does not need takes
room from the reasoning the model was about to do. Whether that trade is worth it
is exactly what running both answers.

The prompt is deliberately UNCHANGED from llm-survivor. Tuning it for JSON would
be a fair thing to try and a different experiment -- two variables moving at once
tells you nothing about either.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot


class RawBot(LLMBot):
    name = "llm-raw"

    # The whole state dict, compact JSON, every turn.
    STATE_VIEW = "json"

    PROMPT = GAME_RULES + """
PLAY LIKE THIS
- Early on you have one Pokemon. If it faints you have lost. Widening the team is
  worth more than any experience you could gain.
- Never walk a Pokemon on low HP into a fight. Heal first if a pokecenter is
  reachable.
- Prefer a wild fight over a trainer when your team is thin: trainers bring more
  Pokemon and scale with the map.
- Type matchups decide battles. Check your team before choosing a fight.

Think briefly, then call `play`. Always call `play`."""
