"""Look before you leap.

Says nothing about how to play, only about what to read first. It is
the cheapest test of whether these models lose runs by choosing badly
or by choosing without looking — and it costs the most tokens, since
every turn spends tool rounds before committing.

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."              # whichever model you want to measure
    uv run pokelike bot run --bot llm-analyst --runs 3

The prompt below is the whole submission. Everything else — the tools, the loop,
how the state is rendered, what happens on a timeout — is in
`pokelike.bot.llm`, shared by every LLM bot so that a difference in results is a
difference between models and prompts rather than between harnesses.

`MODEL` is left unset, so this plays whatever `$MODEL_ID` names and the result
records which model that was. Pin it in your own bot if you want a leaderboard
row that means one specific model for good.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot


class AnalystBot(LLMBot):
    name = "llm-analyst"

    PROMPT = GAME_RULES + """
HOW TO DECIDE
Before choosing, gather what you need:
1. Call `team_details` if any HP or type matchup could matter here.
2. Call `what_lies_ahead` whenever you are on the map. What a node leads to
   matters as much as the node itself, because the others close forever.
Only then call `play`, naming in one sentence the option you rejected and why.

Always finish with `play`."""
