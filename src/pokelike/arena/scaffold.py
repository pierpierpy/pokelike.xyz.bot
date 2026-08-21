"""Creating a new bot: `pokelike bot new <name>`.

Writes a folder that already plays. That is the point — you can benchmark it
before changing a line, so when the number moves you know it moved because of
something you did.
"""

from __future__ import annotations

from pathlib import Path

from ..bot.catalogue import BOTS, available, slugify


def fill(template: str, **fields: str) -> str:
    """Substitutes `{name}`-style placeholders without `str.format`.

    `format` would treat every brace in a template as a field, and a template for
    an LLM bot is full of JSON: the tool schemas are literal `{...}`. Using it
    here meant that adding a commented-out tool example to the template broke
    `bot new` with a KeyError about a JSON key. Plain replacement cannot.
    """
    for key, value in fields.items():
        template = template.replace("{" + key + "}", value)
    return template

TEMPLATE = '''"""{title}

    uv run pokelike bot run --bot {name} --runs 5 -d
    uv run pokelike bot bench --bot {name} --dry-run

A bot is one method: given the state, say which action to take. Everything else
-- starting the browser, applying the move, scoring the run -- is handled for you.

This one heals when somebody is hurt and otherwise walks towards trainers, which
is worth more than random and not much more. Replace it.

WHAT YOU GET TO LOOK AT
`state` is one dict, not a history: what history matters is already inside it.
Every map node carries `visited`, and `stats` are cumulative from the start.

    uv run pokelike schema        prints the whole reference from a live game

THE ONE THING THAT CATCHES EVERYONE
`state["actions"]` is renumbered every turn. Index 2 is a battle now and a catch
next turn, so nothing can be decided by position -- look at what each entry is.

KEEP THIS FILE SELF-CONTAINED
Whatever it needs beyond the `pokelike` package goes in `artifacts/` beside it.
If you train something, freeze the state encoding HERE rather than importing it
from your training code: otherwise improving that code silently changes what
your own past scores meant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"


class {cls}(Bot):
    name = "{name}"

    def choose(self, state: dict[str, Any]) -> int:
        """Which action to take, as an index into state["actions"]."""
        team = state.get("team") or []
        hurt = any(p["hp"] / p["max_hp"] < 0.5 for p in team if p["max_hp"])

        for i, a in enumerate(state["actions"]):
            if hurt and a.get("node") == "pokecenter":
                return i
        for i, a in enumerate(state["actions"]):
            if a.get("node") == "trainer":
                return i
        return 0

    def explain(self) -> str:
        """One line under each decision in the log. Optional."""
        return ""

    # Other optional hooks, all of them safe to ignore:
    #
    #   rearrange(state) -> (a, b) | None   who leads the next battle. Free: it
    #                                       does not consume the turn
    #   on_start(seed) / on_end(state, score)   for a bot with memory
    #   artifacts() -> [Artifact]           weights and config to record beside
    #                                       the result when you benchmark
'''

LLM_TEMPLATE = '''"""{title}

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."              # unless you pin MODEL below
    uv run pokelike bot run --bot {name} --runs 3 -d
    uv run pokelike bot bench --bot {name} --dry-run

Or without exporting anything, with the same three values as flags:

    uv run pokelike bot run --bot {name} --runs 3 -d \\
        --endpoint https://... --api-key @~/.key --model gpt-4o-mini

`--api-key @path` reads the key from a file, which keeps it out of `ps` and out
of your shell history.

THE PROMPT IS THE SUBMISSION
Everything around it lives in `pokelike.bot.llm`: the tools, the agentic loop,
how the state is rendered, one HTTP call per turn, and what happens when a call
fails. That harness is shared by every LLM bot ON PURPOSE -- two bots with
different loops are two harnesses being compared, and the model is the smaller
half of the difference.

So the only thing you have to write is `PROMPT`. `GAME_RULES` is the factual
half, read out of the game bundle rather than guessed; keep it and add your
strategy, or drop it and write your own if you think the facts are the problem.

CREDENTIALS NEVER GO IN THIS FILE
Endpoint and token come from the environment, always. The MODEL ID is not a
secret and you may pin it: doing so puts it inside the fingerprint, so a
leaderboard row means one specific model and swapping the model shows up as a
changed bot. Leave it None and the bot plays whatever $MODEL_ID names.

WHAT TO WATCH IN THE RESULT
`fallback_rate`. Every fallback is a turn the model did not decide, played by the
backup heuristic under your bot's name. A high rate is a broken run, not a bad
model, and reading it as a score is the easiest mistake to make here.
"""

from pokelike.bot.llm import GAME_RULES, LLMBot


class {cls}(LLMBot):
    name = "{name}"

    PROMPT = GAME_RULES + """
PLAY LIKE THIS
- Say something here that a model would not have done on its own. That is the
  whole experiment: `bots/llm-baseline/` is the same harness with no strategy,
  so anything you add is measured against it.

Think briefly, then call `play`. Always call `play`."""

    # Every one of these is optional; these are the defaults.
    #
    # MODEL = None          # pin an id here, or leave $MODEL_ID to name it
    # TEMPERATURE = 0.6
    # MAX_TOKENS = 1500
    # MAX_ROUNDS = 4        # tool rounds before the turn is given up on
    # What the model READS each turn. The default is the ASCII view a person
    # sees; "json" is the whole state dict at about 6.6x the tokens. Which of
    # the two plays better is an open question -- bots/llm-raw/ is the same
    # prompt as bots/llm-survivor/ with only this changed.
    #
    # STATE_VIEW = "screen"   # "json" | "both" | ["team", "actions", ...]
    #
    # def view(self, state):          # when none of the four fit
    #     return f"HP {...}"          # journal and instructions are added for you

    # MEMORY = 6            # past turns shown back to the model
    # TOKEN_BUDGET = 0      # per-run ceiling; 0 means none. ~30k is one run

    # If the prompt is not where your idea lives, give the model a tool the
    # shared four do not offer. `play` must survive -- it is how a turn ends.
    # Your result records that your tools differ, so the row is read as the
    # different question it is rather than compared as if it were the same one.
    #
    # EXTRA_TOOLS = [{
    #     "type": "function",
    #     "function": {
    #         "name": "bag",
    #         "description": "What you are carrying.",
    #         "parameters": {"type": "object", "properties": {}},
    #     },
    # }]
    #
    # def run_tool(self, name, args, state):
    #     if name == "bag":
    #         return ", ".join(state.get("bag") or []) or "(empty)"
    #     return super().run_tool(name, args, state)
'''

README = '''# {name}

_One line on what this bot does and how it decides._

```bash
uv run pokelike bot run --bot {name} --runs 5 -d
uv run pokelike bot bench --bot {name} --dry-run
```

| | |
|---|---|
| how it works | |
| what it scored | run the benchmark and fill this in |
| what was tried and dropped | |
'''


def new_bot(name: str, root: Path | None = None, llm: bool = False) -> Path:
    """Creates `bots/<name>/`, or explains why it cannot.

    With `llm=True` the bot starts from the shared LLM harness instead of an
    empty `choose`, because an LLM bot that reimplements the loop is not
    comparable with the others and the loop is the part nobody wants to write.
    """
    slug = slugify(name)
    base = Path(root) if root else BOTS
    d = base / slug

    if d.exists():
        raise FileExistsError(
            f"{d} already exists. Pick another name, or work on the one that is "
            f"there:\n  uv run pokelike bot run --bot {slug} --runs 5 -d"
        )
    if slug in available(base):
        raise FileExistsError(f"a bot named '{slug}' already exists")

    cls = "".join(part.capitalize() for part in slug.split("-")) + "Bot"
    (d / "artifacts").mkdir(parents=True)
    template = LLM_TEMPLATE if llm else TEMPLATE
    kind = "a prompt to try." if llm else "a starting point."
    (d / "bot.py").write_text(
        fill(template, name=slug, cls=cls, title=f"{slug}: {kind}"),
        encoding="utf-8",
    )
    (d / "README.md").write_text(fill(README, name=slug), encoding="utf-8")
    # Git does not track an empty directory, and a bot with no artifacts is
    # normal — a rules bot needs none — so leave something to keep the shape.
    (d / "artifacts" / ".gitkeep").write_text("", encoding="utf-8")
    return d
