"""The rules, and nothing else.

The control. It is told what the game is and left to work out how to
play it, so every other prompt here can be read as a claim about what
the model does not figure out on its own.

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."              # whichever model you want to measure
    uv run pokelike bot run --bot llm-baseline --runs 3

The prompt below is the whole submission. Everything else — the tools, the loop,
how the state is rendered, what happens on a timeout — is in
`pokelike.bot.llm`, shared by every LLM bot so that a difference in results is a
difference between models and prompts rather than between harnesses.

`MODEL` is left unset, so this plays whatever `$MODEL_ID` names and the result
records which model that was. Pin it in your own bot if you want a leaderboard
row that means one specific model for good.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot


class BaselineBot(LLMBot):
    name = "llm-baseline"

    PROMPT = GAME_RULES + """
Think briefly, then call `play` with your chosen index. Always call `play`."""
