"""Frozen harness for the model benchmark, v5 (HARNESS = 6 internally).

This file is a self-contained LLM bot that inherits from Bot (not LLMBot),
because importing the shared library would let improvements there silently
change what recorded scores mean. Once a result exists under ../results/,
this file must not be edited; a new idea belongs in a new version directory.

The harness asks one model call per turn, carries a cross-run notebook the
model is told to maintain, shows node tooltips, gates the move-tutor block
on the tutor screen, separates what was done from what was said in the
journal, records every tool call per decision, and answers the play() call
before storing the exchange. The note cap is settable with --set notes=N.

Three companion files are frozen beside this one for the same reason:
render.py (what the model reads), bridge.js (what is in the state and the
action order), and init.js (the seeded PRNG and pinned clock). The shared
browser.py, game.py, and runner.py are still imported; their hashes are
recorded in every result and drift is reported rather than absorbed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

# The renderer is the frozen copy beside this file, loaded by path.
# A relative import fails because load_class uses spec_from_file_location with
# no parent package, and all harness directories share the name "harness" so they
# would collide in sys.modules.
_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    f"pokelike_harness_{_HERE.parent.name}_render", _HERE / "render.py"
)
render = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = render
_spec.loader.exec_module(render)

# The harness version written into every result. A row measured under a
# different number is marked as such rather than ranked as if it were the same.
HARNESS = 6


# ---------------------------------------------------------------- what is true
#
# The game rules below are facts shared identically across all bots. Kept here
# so the benchmark measures play quality, not who copied the rules correctly.
# Badges are the goal (the engine's score formula targets Battle Tower, not
# Story mode), and choosing a node closes the others on that layer permanently.

GAME_RULES = """You are playing Pokelike, a Pokemon roguelike autobattler.

You are an experienced Pokemon player: you know the types, their weaknesses, STAB
and stats. But you have NEVER played THIS game before. Its maps, its gyms, which
teams, items and trades actually work here, none of that is known to you at the
start. You learn it only by playing, and by the notes you carry from run to run.

THE GAME
You draft a starter, then cross a branching map made of several stages. Each stage
ends in a Gym Leader; beating one earns a BADGE, and badges are how far you got.
Clear the gyms and you reach the Elite Four, five hard battles back to back.
The twist: BATTLES FIGHT THEMSELVES. You never pick a move in combat. The whole
game is the decisions you make BETWEEN fights: which route to take, who to catch,
which item to hold and on whom, which Pokemon leads the next battle, when to trade,
when to heal. A battle is usually won or lost before it begins, by how you prepared.

YOUR GOAL: earn as many gym badges as you can before your team is wiped out. A run
ends the instant every Pokemon has fainted, no matter how well it was going.

HOW A TURN WORKS
- The map is a layered graph running top to bottom, with the gym (boss) at the
  bottom. You pick one node from the legal ones.
- The moment you pick, every other node on that layer CLOSES FOREVER. The choice
  is irreversible, and it also decides which nodes you can reach on the next layer.
- Your team holds up to 6 Pokemon. Slot 0 leads the next battle.

NODE TYPES
  o catch        adds a Pokemon to your team
  x wild fight   one wild Pokemon, gives experience
  T trainer      1 Pokemon on map 0, 2 on maps 1-2, 3 from map 3 onwards
  i item         an item to equip or keep (some are passive: kept for the whole run)
  + pokecenter   restores your team's HP
  ? unknown      only revealed when you enter it
  $ trade        swap a Pokemon for a stronger one
  M move tutor   teach one of your team a stronger move    S shop    B gym leader

WHAT ACTUALLY KILLS RUNS
Losing Pokemon. Every faint is permanent for that run, and once the team is empty
it is over. Survival comes first: a wiped team scores nothing, however far ahead.

HOW BATTLES ARE DECIDED
You already know Pokemon type matchups, weaknesses and stats. What is specific to
THIS game is that battles are AUTOMATIC, so a fight is decided before it starts by
WHO LEADS (slot 0) and whether its move type beats what is in front of it. The team
view shows each Pokemon's move type, physical or special, and STAB; a node's tooltip
shows the types a trainer or gym uses. Put the right lead in front with `set_lead`
(it is free, it does not cost the turn) before a fight.

FINDING YOUR OWN STRATEGY
Nobody is going to hand you a strategy. How to play this well is FOR YOU TO WORK
OUT, run by run, and to WRITE DOWN: use your notes to record what actually worked
and what lost you a run, then sharpen them as later runs prove them right or wrong.
That growing notebook IS your strategy. A few kinds of note worth keeping:
  - what a given gym used, and which lead beat it;
  - which catches, items or trades paid off, and which wasted a turn;
  - a mistake you do not want to repeat.
Revise a note when a run contradicts it, forget one that stops being true. You know
Pokemon; you do not yet know Pokelike, and this is how you learn it.

BEFORE YOU PLAN, READ YOUR NOTES. They are shown to you every turn; they are what
your past runs learned. Plan the run from them: call `plan` and write it out in as
much detail as you like. There is no limit on the length of your plan or on how much
you think out loud, so spell out the route you mean to take and why, in full.

WHAT YOU REMEMBER, AND FOR HOW LONG
Four different things, with four different lifetimes. Knowing which is which is
most of playing this well.

  1. THIS TURN. The screen above, plus anything you ask a tool.

  2. YOUR LAST FEW TURNS, in full. The exchanges of the previous three turns come
     with you: your own words, the tools you called, what they answered. This is
     why you do not have to re-derive what you worked out a moment ago -- read it
     instead. If you wrote "the team is too weak for the boss, level up first",
     that sentence is still in front of you.

  3. YOUR PLAN FOR THIS MAP, if you write one. Shown every turn until you replace
     it. It dies with the map.

  4. YOUR NOTES, which OUTLIVE THE RUN. This is the only thing that crosses from
     one game into the next. Everything else is gone when your team is wiped out.

YOUR MEMORY IS PART OF PLAYING, NOT AN EXTRA. USE IT.
You get %NOTES% notes of 160 characters. They are shown to you every single turn,
numbered, so you never need to ask for them. You can write, sharpen or drop one on ANY
turn, this one included, and the change is in front of you from the next turn on.

WRITE AT LEAST ONE NOTE IN EVERY RUN. A run that ends with the notebook untouched is a
run you learned nothing from, and the notes are the only thing that survives your team
being wiped out. Everything else -- your reasoning, your plan, what you saw -- is gone.

  `remember` -- a rule you want to be holding next time. Write it the moment you learn
      it, not at the end: there is no end to write at, the run stops the instant your
      last Pokemon faints.
  `revise`   -- when a note turns out to be nearly right, sharpen THAT note. Two vague
      notes about one thing are worth less than one exact note.
  `forget`   -- when a note was wrong, or when you have something better and no room.

Full notebook is not a reason to stop writing. Once you hold %NOTES%, `forget` your
weakest note and `remember` the better one. The cap is there to make you choose, so
treat them as your %NOTES% most valuable beliefs about this game rather than a diary.

NOTES THAT ARE WORTH THE SPACE. Each is a rule for the next run, and each carries a
number or a name:
  "map 0 trainers are safe with a level 8 lead; map 1 trainers carry 2 Pokemon"
  "skipping the pokecenter before the gym lost me 3 runs at exactly 1 badge"
  "Brock leads Geodude Lv12 and Onix Lv14, both Rock: a Water lead walks it"
  "catching at layer 1 costs one turn and pays for itself by the second gym"
  "a level 14 lead loses to Rocket Grunts on map 2; arrive at 17"

NOTES THAT WASTE IT:
  "I am on map 1"            -- false in a minute
  "be careful with trainers" -- no number, so no decision changes
  "I chose the trainer node" -- the journal already tells you that
  "Pokemon have types"       -- you knew that before the run started

WHEN TO WRITE, CONCRETELY:
  * a fight went worse than you expected: write what you had and what beat it
  * your team is nearly gone: write what killed you, NOW, while you still have a turn
  * something you believed turned out wrong: `revise` that note, do not add a second
  * you found something that worked: write the number that made it work

HOW TO PLAY WELL
Nobody has told you the optimal strategy, because nobody knows it. What follows is
sound reasoning from the rules above, and your notes are how you improve on it.

  - LOOK BEFORE YOU CLOSE A DOOR. A map choice closes every alternative on that
    layer forever AND decides what you can reach next, so call `what_lies_ahead`
    before choosing on the map. A node that looks worse but keeps two paths open is
    often better than a slightly better node that funnels you into one.
  - WRITE A PLAN ON EVERY MAP, BEFORE YOUR FIRST CHOICE THERE. Name the nodes and say
    what each is for, so that when a fight goes badly you can see which assumption
    broke. A plan is worth having wrong; it is not worth skipping.
      A plan that helps: "n1_0 catch for a second body, n2_1 trainer for levels,
      skip the item at n3_2, pokecenter n7_0 before the gym"
      A plan that does nothing: "level up and beat the gym"
    Replace it with `plan` the moment the route stops making sense. It is yours, and
    it is shown back to you every turn until you change it.
  - DECIDE THE ROUTE EARLY. Write a `plan` before your first choice on a map, while
    every option is still open. Losing usually traces back to a choice made many
    turns before the turn where you died.
  - LEVEL BEFORE THE BOSS, NOT DURING. Trainers carry more Pokemon than wild fights
    and give correspondingly more experience. The gym is at the bottom of the map,
    you can see it coming, and arriving under-levelled is the common way to stop at
    one badge.
  - HEAL BEFORE THE BOSS. The pokecenter is the only thing that restores HP, and a
    boss fought at half health costs Pokemon you cannot replace.
  - BREADTH EARLY, DEPTH LATER. Early catches are cheap insurance: a team of one is
    one faint from the end of the run. Check `team_details` rather than assuming.
  - THE LEAD MATTERS AND IS FREE. `set_lead` does not consume your turn, so put a
    healthy, well-matched Pokemon in front before a fight instead of after.
"""

CLOSING = """
Before you decide: read your notes above, read what you said in your last turns, and
check your plan.

Two things to have done before this run ends, and you cannot know which turn is the
last one:
  1. a `plan` for the map you are on, naming its nodes
  2. at least one `remember`, or a `revise` of a note this run proved wrong

If neither has happened yet this run, do it in this turn, before you play.

Then call `play` with your chosen index. Always call `play`."""


# ---------------------------------------------------------------------- tools
#
# Shared tools: every bot gets the same set by default. A bot that adds or
# removes tools is marked in the standings so its row is read as a different
# question.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "team_details",
            "description": "Full team stats: HP, levels, types, held items.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "what_lies_ahead",
            "description": (
                "For each legal action, which nodes it leads to on the next layer. "
                "Useful to avoid closing off good paths: this choice decides what "
                "you will be able to do next."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_lead",
            "description": (
                "Move a team member to slot 0, so they enter the next battle first. "
                "Free: it does not use the turn, and you still have to call play "
                "afterwards. Only offered on the map screen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "team slot to promote"},
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Write down something you have learned about this game, to be shown "
                "back to you on every later turn AND in later runs. Use it for "
                "lessons that will still be true next time, not for what is on "
                "screen now. Keep each note short and concrete."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "one lesson, one sentence"},
                },
                "required": ["note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "revise",
            "description": (
                "Replace one of your notes with a better version of it. Use this "
                "when a lesson turns out to be half right: your notes are capped, "
                "so sharpening one is often worth more than adding another."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "which note, as numbered"},
                    "note": {"type": "string", "description": "what it should say instead"},
                },
                "required": ["id", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": (
                "Delete one of your notes. Worth doing when a lesson was wrong, or "
                "when you need the room for a better one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "which note, as numbered"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": (
                "Write down the route you mean to take through this map, and why. "
                "It is shown back to you every turn until you change it, so it is "
                "how a decision made now reaches the turn that has to honour it. "
                "Calling this again replaces it. Choosing a node closes every other "
                "node on that layer forever, so the order you take them in is most "
                "of the game."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": "the plan, in a sentence or two",
                    },
                },
                "required": ["route"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play",
            "description": "Perform the chosen action and end the turn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "index of the legal action"},
                    "why": {"type": "string", "description": "one sentence on the reason"},
                },
                "required": ["index", "why"],
            },
        },
    },
]


_STOCK_TOOL_NAMES = [t["function"]["name"] for t in TOOLS]


class LLMError(RuntimeError):
    """Something went wrong on one call. Recoverable: fall back and play on."""


class LLMConfigError(LLMError):
    """The setup is wrong and every call will fail the same way.

    Falling back on these would play a whole run on the backup heuristic and
    file it as an LLM result no model ever played, so these stop the run.
    """


class LLMBudgetError(LLMError):
    """The run exceeded its declared token budget (TOKEN_BUDGET).

    Raised so the run stops cleanly rather than silently handing the rest to
    the backup heuristic.
    """


# ------------------------------------------------------------------------ bot


class HarnessV4(Bot):
    """A bot that asks a model what to do, one call per turn.

    Subclass and set `PROMPT`. Everything else has a working default.

    | attribute      | what it decides                                        |
    |----------------|--------------------------------------------------------|
    | `PROMPT`       | the system prompt (this is the submission)             |
    | `MODEL`        | model id, or None to take `$MODEL_ID`                  |
    | `TEMPERATURE`  | sampling temperature                                   |
    | `MAX_TOKENS`   | ceiling on one answer                                  |
    | `MAX_ROUNDS`   | tool rounds before the turn is given up                |
    | `MEMORY`       | how many past turns are shown back to the model        |
    | `TOKEN_BUDGET` | tokens per run, 0 for no ceiling                       |
    | `EXTRA_TOOLS`  | tools on top of the shared eight                       |
    | `STATE_VIEW`   | what the model reads each turn                         |

    `STATE_VIEW` options:

    | value | what the model gets | roughly |
    |---|---|--:|
    | `"screen"` | the ASCII view a person sees (default) | 880 chars |
    | `"json"` | the whole state dict, compact JSON | 5900 chars |
    | `"both"` | the view, then the dict under it | 6800 chars |
    | `["team", "actions"]` | just those keys, as JSON | varies |

    Override `render_state(state)` for anything the settings do not cover.

    To add tools, declare them in `EXTRA_TOOLS` and answer them in
    `answer_tool`. Replacing the shared set entirely is `tools()`. Both are
    recorded: a bot with its own tools is answering a different question, and
    the standings say so.

    Pinning `MODEL` in the bot file puts the model id inside the fingerprint.
    Leaving it None means the bot plays whatever `$MODEL_ID` names.
    """

    name = "llm-bench-v2"

    HARNESS = HARNESS
    PROMPT = GAME_RULES + CLOSING
    MODEL: str | None = None
    TEMPERATURE = 0.0
    # High ceiling so output length never ends a turn.
    MAX_TOKENS = 16000
    # Six rounds so the model can curate notes before calling play() without
    # exhausting its rounds and falling back.
    MAX_ROUNDS = 6
    MEMORY = 6
    TOKEN_BUDGET = 0
    # Retries for transient failures (rate limits, 5xx). Without retries a 429
    # would count as a turn the model failed to answer.
    RETRIES = 4
    # Notes survive on_start, crossing from one run into the next. A pass is
    # therefore one lifetime of fifty runs.
    CROSS_RUN_MEMORY = True
    NOTES_MAX = 12
    NOTE_CHARS = 160
    # How many finished exchanges travel to the next turn verbatim. Three keeps
    # recent context without unbounded request growth; older turns appear in the
    # journal as one-line summaries.
    SCRATCH_TURNS = 3
    # The route the model commits to for the current map. Per run, not per turn:
    # the map is visible ahead and each choice closes a layer permanently.
    PLAN_CHARS = 1200
    EXTRA_TOOLS: list[dict[str, Any]] = []
    STATE_VIEW: Any = "screen"

    def __init__(self, seed: int = 0, endpoint: str | None = None,
                 token: str | None = None, model: str | None = None,
                 verbose: bool = False, **overrides: Any) -> None:
        super().__init__(seed=seed)
        self.endpoint = (endpoint or os.environ.get("FW_ENDPOINT", "")).rstrip("/")
        self.token = token or os.environ.get("FW_TOKEN", "")
        self.model = model or self.MODEL or os.environ.get("MODEL_ID", "")
        if not self.endpoint or not self.token:
            raise LLMConfigError(
                "FW_ENDPOINT and FW_TOKEN environment variables are required\n"
                '  export FW_ENDPOINT="https://..."   # base URL, no /v1\n'
                '  export FW_TOKEN="..."'
            )
        if not self.model:
            raise LLMConfigError(
                f"{type(self).__name__} pins no MODEL, so MODEL_ID is required\n"
                '  export MODEL_ID="gpt-4o-mini"'
            )

        # Per-instance copies of the class settings, so a caller can override
        # without editing the bot file. The prompt uses %NOTES% as a placeholder
        # for the cap, substituted with str.replace (not str.format, because
        # prompts contain braces).
        self.notes_max = int(overrides.pop("notes", None) or self.NOTES_MAX)
        if self.notes_max < 1:
            raise LLMConfigError("notes must be at least 1")
        self.system = (overrides.pop("prompt", None)
                       or self.PROMPT).replace("%NOTES%", str(self.notes_max))
        self.temperature = overrides.pop("temperature", self.TEMPERATURE)
        self.max_tokens = overrides.pop("max_tokens", self.MAX_TOKENS)
        self.max_rounds = overrides.pop("max_rounds", self.MAX_ROUNDS)
        self.memory = overrides.pop("memory", self.MEMORY)
        # Settable per instance so experiments can compare views on the same
        # seeds. A submission should declare it on the class so the fingerprint
        # covers it.
        self.state_view = overrides.pop("view", None) or self.STATE_VIEW
        self.token_budget = overrides.pop("token_budget", self.TOKEN_BUDGET)
        if overrides:
            raise TypeError(f"unknown settings: {', '.join(sorted(overrides))}")
        self.verbose = verbose or bool(os.environ.get("POKELIKE_VERBOSE"))

        # Without `play` the model cannot end a turn, so every turn would exhaust
        # its rounds and fall back silently.
        names = self.tool_names()
        if "play" not in names:
            raise LLMConfigError(
                f"{type(self).__name__}.tools() offers no `play` tool "
                f"({', '.join(names) or 'nothing'}).\n"
                "  It is how the model ends a turn; without it every turn falls back."
            )
        if len(names) != len(set(names)):
            raise LLMConfigError(
                f"{type(self).__name__} declares a tool twice: "
                f"{', '.join(sorted({n for n in names if names.count(n) > 1}))}.\n"
                "  Providers reject a duplicated function name."
            )

        self.calls = 0
        self.turns = 0
        self.tokens_used = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.retries = 0
        self.fallbacks = 0
        self.journal: list[str] = []
        # Cross-run notebook. Not cleared by on_start (CROSS_RUN_MEMORY).
        self.notebook: list[str] = []
        # Tool calls since the last decision was logged, drained by
        # tool_calls_made(). Not cleared per turn because reorder() runs before
        # act() and its calls belong to the same decision.
        self.tool_log: list[dict[str, Any]] = []
        # Per-run state: the plan is about this map, the scratchpad is this
        # episode's reasoning. Only the notebook crosses a run boundary.
        self.plan: str = ""
        self.scratch: list[list[dict[str, Any]]] = []
        self._last_why = ""
        # The turn decided in `rearrange`, waiting for `choose` to collect it.
        self._pending: tuple[int | None, int | None, str] | None = None

    # ------------------------------------------------------------------ hooks

    def reset(self, seed: int) -> None:
        self.seed = seed
        # The journal is within-run; the notebook stays (CROSS_RUN_MEMORY).
        self.journal = []
        # Per-run state resets. The notebook is not touched.
        self.plan = ""
        self.scratch = []
        self._pending = None
        self.calls = self.turns = self.tokens_used = self.fallbacks = 0
        self.tokens_in = self.tokens_out = self.retries = 0
        self._last_why = ""

    def metadata(self) -> dict[str, Any]:
        """Data written into the run registry and into a benchmark result.

        The `fallback_rate` column is the honest signal: each fallback is a turn
        the backup heuristic played under the model's name.
        """
        return {
            "model": self.model,
            "harness": self.HARNESS,
            "bot": type(self).__name__,
            "calls": self.calls,
            "turns": self.turns,
            "tokens": self.tokens_used,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            # Transient failures that were retried.
            "retries": self.retries,
            "fallbacks": self.fallbacks,
            # Saved with every run so note evolution is visible.
            "notebook": list(self.notebook),
            "notes_kept": len(self.notebook),
            # The cap this pass ran under (settable, so it must be recorded).
            "notes_max": self.notes_max,
            # Per-run plan and scratchpad depth.
            "plan": self.plan,
            "scratch_turns": len(self.scratch),
            "fallback_rate": round(self.fallbacks / self.turns, 3) if self.turns else 0.0,
            "temperature": self.temperature,
            # False if the bot uses non-standard tools.
            "stock_tools": self.tool_names() == _STOCK_TOOL_NAMES,
            # Two rows with different views are not comparable.
            "state_view": self.view_name(),
            "reproducible": False,
        }

    def tool_names(self) -> list[str]:
        return [t["function"]["name"] for t in self.tools()]

    def artifacts(self) -> list:
        """The prompt and model reference carried by a submission of this bot.

        LLM results are not exactly reproducible (providers change models behind
        a fixed name and sampling is stochastic), so these record what was asked.
        """
        from pokelike.arena.leaderboard import Artifact

        return [
            Artifact(
                name="prompt.md",
                kind="prompt",
                description=f"system prompt, {type(self).__name__}",
                text=self.system,
            ),
            Artifact(
                name="model.json",
                kind="model-ref",
                description="which model answered, and how it was asked",
                data={
                    "model": self.model,
                    "pinned": self.MODEL is not None,
                    "harness": self.HARNESS,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "max_rounds": self.max_rounds,
                    "memory": self.memory,
                    "scratch_turns": self.SCRATCH_TURNS,
                    "plan_chars": self.PLAN_CHARS,
                    "token_budget": self.token_budget,
                    "tools": self.tool_names(),
                    "stock_tools": self.tool_names() == _STOCK_TOOL_NAMES,
                    "state_view": self.view_name(),
                    "reproducible": False,
                    "why_not": (
                        "providers change models behind a fixed name and sampling is "
                        "stochastic; rerunning this will not give identical results"
                    ),
                },
            ),
        ]

    # --------------------------------------------------------------- decision

    def reason(self) -> str:
        return self._last_why

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Decide the lead in the same model call as the move.

        The run loop calls reorder() before act(), so the agentic round runs
        here. The chosen action is cached and act() returns it without a second
        request. Offered only on the map screen, because elsewhere the options
        ARE the team and reordering would change what an index means.
        """
        self._pending = None
        if state.get("screen") != "map-screen" or not state.get("can_reorder"):
            return None
        try:
            index, why, lead = self._agentic_round(state, allow_lead=True)
        except LLMConfigError:
            raise
        except Exception:  # noqa: BLE001, handled again and counted in choose
            return None
        team = state.get("team") or []
        if lead is None or not 0 < lead < len(team):
            self._pending = (state.get("steps"), index, why)
            return None
        # The lead decision is merged into the act() explanation.
        why = f"lead {team[lead]['name']} | {why}"
        self._pending = (state.get("steps"), index, why)
        return (0, lead)

    def act(self, state: dict[str, Any]) -> int:
        self.turns += 1
        n = len(state["actions"])
        # Already decided in reorder() for this same step.
        if self._pending and self._pending[0] == state.get("steps"):
            _, index, why = self._pending
            self._pending = None
            if isinstance(index, int) and 0 <= index < n:
                return self._commit(state, index, why)
        try:
            index, why, _ = self._agentic_round(state)
        except (LLMConfigError, LLMBudgetError):
            # Not recoverable: every later call fails identically, or the run has
            # spent what it was allowed. Better to stop than to quietly hand the
            # rest of the run to the backup heuristic and file it as an LLM run.
            raise
        except Exception as e:  # noqa: BLE001, a transient failure must not end the run
            return self._run_fallback(state, f"{type(e).__name__}: {e}"[:80])

        if not isinstance(index, int) or not 0 <= index < n:
            return self._run_fallback(state, f"model returned index {index}")
        return self._commit(state, index, why)

    def _commit(self, state: dict[str, Any], index: int, why: str) -> int:
        self._last_why = why
        self.journal.append(self._journal_entry(state, index, why))
        self.journal = self.journal[-self.memory:]
        if self.verbose:
            print(f"   [llm] -> [{index}] {why[:100]}")
        return index

    def _journal_entry(self, state: dict[str, Any], index: int, why: str) -> str:
        """One past turn for the journal: the action taken (from the state) and
        the model's own sentence (labelled separately so the model can tell fact
        from its own reasoning).
        """
        actions = state.get("actions") or []
        act = actions[index] if 0 <= index < len(actions) else {}
        if act.get("kind") == "node":
            did = f"node {act.get('id', '?')} ({act.get('node', 'node')})"
            if act.get("tooltip"):
                did += f", {act['tooltip']}"
        else:
            did = str(act.get("label") or act.get("id") or "action")
        said = " ".join(str(why or "").split())[:200]
        return (f"step {state.get('steps')}: [{index}] {did}\n"
                f"    it said: {said or '(nothing)'}")

    def _run_fallback(self, state: dict[str, Any], reason: str) -> int:
        self.fallbacks += 1
        self._last_why = f"(fell back: {reason})"
        if self.verbose:
            print(f"   [llm] fallback: {reason}")
        return self.fallback_move(state)

    def fallback_move(self, state: dict[str, Any]) -> int:
        """Backup choice when the model does not answer or returns an invalid index.

        Prefers what keeps the team alive: healing first if someone is hurt,
        otherwise widening the team.
        """
        actions = state["actions"]
        team = state.get("team") or []
        hurt = [p for p in team if p["max_hp"] and p["hp"] / p["max_hp"] < 0.4]

        order = ["pokecenter", "catch", "item"] if hurt else ["catch", "item", "pokecenter"]
        for kind in order:
            for i, a in enumerate(actions):
                if a.get("node") == kind:
                    return i
        return 0

    # ---------------------------------------------------------- agentic loop

    def _agentic_round(self, state: dict[str, Any],
                       allow_lead: bool = False) -> tuple[int, str, int | None]:
        """One turn of thinking. Returns (action index, reason, lead or None)."""
        lead: int | None = None
        # The last SCRATCH_TURNS exchanges come along verbatim so the model sees
        # its own recent reasoning. Bounded to avoid unbounded request growth.
        history: list[dict[str, Any]] = [m for turn in self.scratch for m in turn]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system},
            *history,
            {"role": "user", "content": self._situation(state)},
        ]
        # What this turn adds to the scratchpad, kept apart from `messages` so the
        # system prompt and the older turns are not copied into it again.
        this_turn: list[dict[str, Any]] = [messages[-1]]

        for _ in range(self.max_rounds):
            msg = self.call_model(messages)
            calls = msg.get("tool_calls") or []
            if not calls:
                # No tool: maybe it wrote the index out in prose.
                index = self._index_from_text(msg.get("content") or "", len(state["actions"]))
                if index is not None:
                    return index, "(read from prose)", lead
                raise LLMError("the model called no tool")

            spoke = {"role": "assistant", "content": msg.get("content") or "",
                     "tool_calls": calls}
            messages.append(spoke)
            this_turn.append(spoke)

            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                self._note_call(name, args)

                if name == "play":
                    # The turn ends. Every call in the exchange is answered first
                    # (including this one and any after it), so the stored exchange
                    # is a valid conversation any provider accepts.
                    answered = {m.get("tool_call_id") for m in this_turn
                                if m.get("role") == "tool"}
                    for other in calls:
                        if other["id"] in answered:
                            continue
                        this_turn.append({
                            "role": "tool", "tool_call_id": other["id"],
                            "content": (f"played index {args.get('index')}."
                                        if other is c else
                                        "not run: the turn ended at play().")})
                    self._remember_turn(this_turn)
                    return args.get("index"), str(args.get("why", "")), lead

                if name == "set_lead":
                    # Recorded; the run loop performs the actual swap.
                    want = args.get("index")
                    if allow_lead and isinstance(want, int):
                        lead = want
                        reply = f"ok, slot {want} will lead. Now call play()."
                    else:
                        reply = ("not available on this screen: the options here are "
                                 "your team, so reordering would change what an index "
                                 "means. Call play().")
                    answer = {"role": "tool", "tool_call_id": c["id"], "content": reply}
                    messages.append(answer)
                    this_turn.append(answer)
                    continue

                answer = {"role": "tool", "tool_call_id": c["id"],
                          "content": self.answer_tool(name, args, state)}
                messages.append(answer)
                this_turn.append(answer)

        # Rounds exhausted. The exchange is kept so the next turn can see what
        # went wrong rather than repeating it.
        self._remember_turn(this_turn)
        raise LLMError(f"no call to play() within {self.max_rounds} rounds")

    def _remember_turn(self, turn: list[dict[str, Any]]) -> None:
        """Adds one finished exchange to the scratchpad, dropping the oldest.

        The user message (the screen render) is replaced by a placeholder before
        storage, because a stale screen would invite the model to reason about a
        map that has already changed and the current one is in the fresh message.
        """
        kept = [
            {"role": "user",
             "content": "[the screen you were shown that turn, since changed]"}
            if m.get("role") == "user" else m
            for m in turn
        ]
        self.scratch.append(kept)
        self.scratch = self.scratch[-self.SCRATCH_TURNS:] if self.SCRATCH_TURNS else []

    # ------------------------------------------------------------------ tools

    def tools(self) -> list[dict[str, Any]]:
        """The tools offered to the model, in OpenAI function-calling form.

        The shared eight plus EXTRA_TOOLS. Override to replace, but `play` must
        survive or every turn falls back.
        """
        return [*TOOLS, *self.EXTRA_TOOLS]

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call; the return value is shown to the model.

        Override for custom tools and call super() for the shared ones. An
        unknown name gets an error message rather than an exception, so the
        model can try again.
        """
        if name == "team_details":
            return render.team_view(state.get("team")) or "(empty team)"
        if name == "what_lies_ahead":
            return self._exits(state)
        if name in ("remember", "revise", "forget"):
            return self._remember(name, args)

        if name == "plan":
            # Truncated rather than refused: a truncated plan is still useful.
            route = str(args.get("route") or "").strip().replace("\n", " ")
            if not route:
                return "nothing to plan: `route` was empty."
            had, self.plan = bool(self.plan), route[: self.PLAN_CHARS]
            return (("plan replaced. " if had else "plan noted. ")
                    + "You will see it every turn until you change it.")
        return f"unknown tool: {name}"

    # --------------------------------------------------------------- memory

    def _remember(self, verb: str, args: dict[str, Any]) -> str:
        """Handle the three memory verbs (remember, revise, forget).

        Every reply states the current count so the model knows capacity.
        Notes are truncated rather than rejected when too long.
        """
        note = str(args.get("note") or "").strip().replace("\n", " ")
        note = note[: self.NOTE_CHARS]

        if verb == "remember":
            if not note:
                return self._refused("empty note",
                                     "nothing to remember: `note` was empty.")
            if len(self.notebook) >= self.notes_max:
                return self._refused(
                    "notes full",
                    f"your notes are full ({self.notes_max}). Use `revise` to "
                    f"improve one or `forget` to make room, then try again.")
            self.notebook.append(note)
            self._kept()
            return (f"noted as [{len(self.notebook)}]. "
                    f"{len(self.notebook)}/{self.notes_max} notes used.")

        # The id is 1-based (matching what the model is shown). Out-of-range
        # ids are answered with an error message rather than raised.
        try:
            i = int(args.get("id"))
        except (TypeError, ValueError):
            return self._refused(
                "no id",
                f"`id` must be a number between 1 and {len(self.notebook)}.")
        if not 1 <= i <= len(self.notebook):
            return self._refused(
                "no such note",
                f"there is no note [{i}]. You have {len(self.notebook)}: "
                f"use a number between 1 and {len(self.notebook)}.")

        if verb == "forget":
            gone = self.notebook.pop(i - 1)
            self._kept(dropped=gone)
            return (f"forgotten: {gone[:60]}. "
                    f"{len(self.notebook)}/{self.notes_max} notes used, and they have "
                    f"been renumbered.")
        if not note:
            return self._refused("empty note",
                                 "nothing to revise it to: `note` was empty.")
        was = self.notebook[i - 1]
        self.notebook[i - 1] = note
        self._kept(was=was)
        return (f"note [{i}] rewritten. "
                f"{len(self.notebook)}/{self.notes_max} notes used.")

    # ------------------------------------------------------------ the record

    def _note_call(self, name: str, args: dict[str, Any]) -> None:
        """Record one tool call as it is made, before it executes.

        Recorded here (not in answer_tool) so that play, set_lead, and
        invented names are also captured.
        """
        entry: dict[str, Any] = {"tool": name}
        for k in ("index", "id", "slot", "note", "route", "why"):
            v = args.get(k)
            if v not in (None, ""):
                entry[k] = v if not isinstance(v, str) else v[: self.NOTE_CHARS]
        self.tool_log.append(entry)

    def _kept(self, **what: Any) -> None:
        """Marks the call just recorded as having changed the notes."""
        if self.tool_log:
            self.tool_log[-1]["kept"] = len(self.notebook)
            self.tool_log[-1].update(
                {k: str(v)[: self.NOTE_CHARS] for k, v in what.items() if v})

    def _refused(self, why: str, reply: str) -> str:
        """Mark the last tool call as refused and return the error message."""
        if self.tool_log:
            self.tool_log[-1]["refused"] = why
            self.tool_log[-1]["kept"] = len(self.notebook)
        return reply

    def tool_calls_made(self) -> list[dict[str, Any]]:
        """Return and clear all tool calls since last asked.

        Drained per decision (not per turn) because reorder() can also make
        calls that belong to the same decision.
        """
        out, self.tool_log = self.tool_log, []
        return out

    def _memory_block(self) -> list[str]:
        """The notes as the model sees them, numbered 1-based for revise/forget."""
        if not self.notebook:
            return ["", "WHAT YOU HAVE LEARNED SO FAR: nothing yet. Use `remember` "
                    "when you learn something that will still be true next run."]
        return ["", f"WHAT YOU HAVE LEARNED (kept across runs, "
                    f"{len(self.notebook)}/{self.notes_max}):",
                *(f"  [{i}] {n}" for i, n in enumerate(self.notebook, 1))]

    def _plan_block(self) -> list[str]:
        """The model's committed route for this map, shown every turn."""
        if not self.plan:
            return ["", "YOUR PLAN FOR THIS MAP: none yet. Use `plan` to write the "
                    "route you mean to take, before the first choice closes options "
                    "you wanted."]
        return ["", f"YOUR PLAN FOR THIS MAP (yours, change it with `plan`): "
                    f"{self.plan}"]

    # ---------------------------------------------------------------- context

    def render_state(self, state: dict[str, Any]) -> str:
        """What the model reads each turn, controlled by STATE_VIEW.

        Override for anything the four presets do not cover. The harness adds
        the journal and the instruction line around whatever this returns.
        """
        spec = self.state_view
        if isinstance(spec, str) and spec == "screen":
            return render.screen(state)
        if isinstance(spec, str) and spec in ("json", "both"):
            raw = json.dumps(state, separators=(",", ":"))
            if spec == "json":
                return raw
            return f"{render.screen(state)}\n\nTHE SAME STATE, IN FULL:\n{raw}"
        if isinstance(spec, (list, tuple)):
            missing = [k for k in spec if k not in state]
            if missing:
                # A key can be absent on some screens (e.g. `map` during battle).
                if self.verbose:
                    print(f"   [llm] STATE_VIEW: no {', '.join(missing)} on this screen")
            return json.dumps({k: state[k] for k in spec if k in state},
                              separators=(",", ":"))
        raise LLMConfigError(
            f"STATE_VIEW is {spec!r}. Use 'screen', 'json', 'both', a list of "
            f"state keys, or override view(state) yourself."
        )

    def view_name(self) -> str:
        """What to record: the setting, or 'custom' if `view` was replaced."""
        if type(self).render_state is not HarnessV4.render_state:
            return "custom"
        return self.state_view if isinstance(self.state_view, str) else \
            "keys:" + ",".join(self.state_view)

    def _situation(self, state: dict[str, Any]) -> str:
        """The full user message: the rendered view, memory, plan, journal, and
        instruction line. Not intended as an override point; use render_state().
        """
        parts = [self.render_state(state)]
        # Notes before journal: cross-run lessons outrank recent within-run turns.
        parts += self._memory_block()
        parts += self._plan_block()
        if self.journal:
            parts += [
                "",
                "WHAT YOU DID, AND WHAT YOU SAID AT THE TIME.",
                "The action on each first line is the game's record. The sentence "
                "under it is your own from that turn: it is what you meant to do, "
                "not something that has been verified since.",
                *(f"  {r}" for r in self.journal),
            ]
        parts += [
            "",
            f"Pick an index between 0 and {len(state['actions']) - 1} and call play().",
        ]
        return "\n".join(parts)

    def _exits(self, state: dict[str, Any]) -> str:
        """Where each legal action leads, by reading the map's edges."""
        m = state.get("map")
        if not m:
            return "You are not on the map: this choice opens or closes no paths."
        by_id = {n["id"]: n for n in m["nodes"]}
        rows = []
        for i, a in enumerate(state["actions"]):
            if a.get("kind") != "node":
                rows.append(f"  [{i}] {a.get('label', '')[:60]}")
                continue
            after = [by_id[t]["kind"] for f, t in m["edges"] if f == a["id"] and t in by_id]
            follows = ", ".join(sorted(after)) if after else "nothing (end of map)"
            rows.append(f"  [{i}] {a['node']:<12} -> leads to: {follows}")
        return "Exits on the next layer:\n" + "\n".join(rows)

    # ------------------------------------------------------------------- HTTP

    def call_model(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if self.token_budget and self.tokens_used >= self.token_budget:
            raise LLMBudgetError(
                f"run spent {self.tokens_used} tokens, budget is {self.token_budget}"
            )
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": self.tools(),
            "tool_choice": "auto",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            # Best-effort reproducibility seed. Most providers ignore it.
            "seed": self.seed,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.endpoint}/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        # Retried with backoff for transient failures. Auth and model-not-found
        # are not retried because they fail identically every time.
        answer: dict[str, Any] | None = None
        for attempt in range(self.RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    answer = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode("utf-8", "replace")
                if e.code in (401, 403):
                    raise LLMConfigError(
                        f"HTTP {e.code} from {self.endpoint}: the endpoint rejected the "
                        f"token.\n  Check FW_TOKEN, a placeholder left in place looks "
                        f"exactly like this.\n  {detail}"
                    ) from e
                if e.code == 404:
                    raise LLMConfigError(
                        f"HTTP 404 from {self.endpoint}/v1/chat/completions.\n"
                        f"  Either the endpoint is not an OpenAI-compatible API, or it "
                        f"does not serve MODEL_ID={self.model!r}.\n  {detail}"
                    ) from e
                if e.code in (408, 409, 425, 429, 500, 502, 503, 504) \
                        and attempt < self.RETRIES:
                    self.retries += 1
                    time.sleep(min(2 ** attempt, 30) + random.random())
                    continue
                raise LLMError(f"HTTP {e.code}: {detail}") from e
            except Exception as e:  # network, timeout, malformed JSON
                if attempt < self.RETRIES:
                    self.retries += 1
                    time.sleep(min(2 ** attempt, 30) + random.random())
                    continue
                raise LLMError(f"{type(e).__name__}: {e}") from e
        if answer is None:
            raise LLMError("no answer after retries")

        self.calls += 1
        usage = answer.get("usage") or {}
        # Input and output tracked separately because they are priced differently.
        self.tokens_in += usage.get("prompt_tokens", 0)
        self.tokens_out += usage.get("completion_tokens", 0)
        self.tokens_used += usage.get(
            "total_tokens",
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
        )
        choices = answer.get("choices") or []
        if not choices:
            raise LLMError("response had no choices")
        return choices[0].get("message") or {}

    @staticmethod
    def _index_from_text(text: str, n: int) -> int | None:
        """Last resort: fish a valid index out of a prose answer."""
        import re

        for m in re.finditer(r"\[?(\d+)\]?", text):
            v = int(m.group(1))
            if 0 <= v < n:
                return v
        return None
