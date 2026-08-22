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

    def act(self, state: dict[str, Any]) -> int:
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

    def reason(self) -> str:
        """One line under each decision in the log. Optional."""
        return ""

    # Other optional hooks, all of them safe to ignore:
    #
    #   reorder(state) -> (a, b) | None     who leads the next battle. Free: it
    #                                       does not consume the turn
    #   reset(seed) / finish(state, score)  for a bot with memory
    #   metadata() -> dict                  extra facts recorded beside the result
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

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig


class {cls}(LLMBot):
    name = "{name}"

    config = LLMConfig(
        prompt=GAME_RULES + """
PLAY LIKE THIS
- Say something here that a model would not have done on its own. That is the
  whole experiment: `bots/llm-baseline/` is the same harness with no strategy,
  so anything you add is measured against it.

Think briefly, then call `play`. Always call `play`.""",
        # --- notebook: the model writes notes that survive across runs ---
        # Set to 0 to disable the notebook and the three memory tools entirely.
        notes_cap=12,
        note_chars=160,
        cross_run_memory=True,
        # --- plan: the model writes a route it sees every turn ---
        # Set to 0 to disable the plan tool.
        plan_chars=1200,
        # --- bag: let the model ask what items it carries ---
        bag_tool=True,
        # --- scratchpad: carry the last N turns as real messages ---
        # The model sees its own words, not only the one-line journal summary.
        scratch_turns=3,
        # --- more rounds: the memory tools need room ---
        max_rounds=6,
        max_tokens=4000,
    )

    # Every field is optional; these are the defaults. Set the ones you want in
    # the LLMConfig above:
    #
    #   config = LLMConfig(
    #       prompt=...,
    #       model=None,          # pin an id, or leave $MODEL_ID to name it
    #       temperature=0.6,
    #       max_tokens=4000,
    #       max_rounds=6,        # tool rounds before the turn is given up on
    #       memory=6,            # past turns shown back to the model
    #       token_budget=0,      # per-run ceiling; 0 = none. ~30k is one run
    #       state_view="screen", # "json" | "both" | ["team", "actions", ...]
    #       notes_cap=12,        # max notes; 0 = disabled
    #       note_chars=160,      # character limit per note
    #       cross_run_memory=True,  # notes survive between runs
    #       plan_chars=1200,     # max plan length; 0 = disabled
    #       bag_tool=True,       # offer the bag tool
    #       scratch_turns=3,     # last N turns as real messages; 0 = off
    #       extra_tools=[...],   # your tools on top of the shared ones
    #   )
    #
    # `state_view` is what the model READS each turn. The default is the ASCII
    # view a person sees; "json" is the whole state dict at about 6.6x the
    # tokens -- bots/llm-raw/ is bots/llm-survivor/ with only this changed.
    #
    # def render_state(self, state):     # when none of the state_view values fit
    #     return f"HP {...}"             # journal and instructions are added for you

    # If the prompt is not where your idea lives, give the model a tool the
    # shared ones do not offer, via config.extra_tools. `play` must survive --
    # it is how a turn ends. Your result records that your tools differ, so the
    # row is read as the different question it is.
    #
    # def answer_tool(self, name, args, state):
    #     if name == "my_tool":
    #         return "something useful"
    #     return super().answer_tool(name, args, state)
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
