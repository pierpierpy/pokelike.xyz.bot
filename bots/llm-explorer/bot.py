"""Push down the map.

The opposite bet to `llm-survivor`: badges only come from going
further, and a team kept perfectly healthy on safe nodes scores
exactly zero. Worth having both measured rather than argued about.

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."              # whichever model you want to measure
    uv run pokelike bot run --bot llm-explorer --runs 3

The prompt below is the whole submission. Everything else — the tools, the loop,
how the state is rendered, what happens on a timeout — is in
`pokelike.bot.llm`, shared by every LLM bot so that a difference in results is a
difference between models and prompts rather than between harnesses.

`MODEL` is left unset, so this plays whatever `$MODEL_ID` names and the result
records which model that was. Pin it in your own bot if you want a leaderboard
row that means one specific model for good.
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
