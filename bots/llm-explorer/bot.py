"""llm-explorer: push down the map.

The opposite bet to llm-survivor: badges only come from going further, and a team
kept perfectly healthy on safe nodes scores exactly zero. Worth having both
measured rather than argued about.

Credentials come from `.env` at the repository root.

The prompt is the whole submission. The tools, the loop, the rendering and the
timeout policy are shared (`pokelike.bot.llm`), so a difference in results is a
difference between models and prompts, not between harnesses.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class ExplorerBot(LLMBot):
    name = "llm-explorer"

    config = LLMConfig(prompt=GAME_RULES + """
PLAY LIKE THIS
- Badges are the only thing that counts, and they come from pushing down the map.
  Do not linger on safe nodes that add nothing.
- Before choosing, use `what_lies_ahead`: the node you take decides what is
  reachable next, and closing off a good branch costs more than one bad fight.
- A slightly risky fight that opens a good path beats a safe node that leads
  nowhere.
- Keep enough team to survive, but survival on its own scores nothing.

Think briefly, then call `play`. Always call `play`.""")
