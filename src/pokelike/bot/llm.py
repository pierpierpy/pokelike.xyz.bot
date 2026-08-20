"""The harness every LLM bot shares.

An LLM bot is a prompt and a model. Everything around them — how the state
becomes text, which tools exist, how many rounds of thinking are allowed, what
happens when a call fails — is machinery, and it lives here rather than in each
bot, for one reason: **a benchmark of models has to hold the harness still.**
Two bots with different loops are not two models being compared, they are two
harnesses, and the model is the smaller half of the difference.

So a bot built on this is short:

    from pokelike.bot.llm import LLMBot, GAME_RULES

    class SurvivorBot(LLMBot):
        name = "llm-survivor"
        PROMPT = GAME_RULES + "Heal before it is urgent. Always call play()."

Credentials never appear in a bot file. They come from the environment, always:

    export FW_ENDPOINT="https://..."     # base URL; /v1/chat/completions is added
    export FW_TOKEN="..."
    export MODEL_ID="..."                # unless the bot pins MODEL itself
    uv run pokelike bot --bot llm-survivor --runs 3

**This file is shared, which is the thing to be careful about.** The whole point
of a bot being self-contained is that improving our code cannot silently change
what a past measurement meant. Code in here is the exception: it is shared on
purpose, so editing it *does* reach every LLM bot ever measured. `HARNESS` is
how that stays honest — it is written into every result, and a result recorded
under an older harness is flagged in the standings instead of quietly being
compared against results from a newer one. **Bump it whenever a change here
could move a decision.**

Why `urllib` and not a client library: the package has two dependencies, and an
LLM bot should not add a third. One wire format, OpenAI-compatible, which nearly
every provider speaks — including Anthropic, through its compatibility endpoint.
A multi-provider abstraction would be more code to maintain and one more place
for two models to be asked subtly different questions.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

from pokelike.bot.base import Bot
from pokelike.core import render

# How a decision is made here. Written into every result; a row measured under a
# different number is marked as such rather than ranked as if it were the same.
#
#   1  agentic loop with team_details / what_lies_ahead / set_lead / play,
#      situation rendered by core.render.screen, prose index as a last resort
HARNESS = 1


# ---------------------------------------------------------------- what is true
#
# The rules are shared, the strategy is not. The split matters: everything below
# is a FACT about the game, several of them read out of the bundle rather than
# guessed, and a benchmark where each bot restates the facts measures who copied
# them correctly instead of who plays better.
#
# The two that are easy to get wrong, and were:
#
#   * BADGES ARE THE GOAL. The engine's score formula was written for the Battle
#     Tower and two of its six terms never fire in Story mode, so a prompt that
#     chases "maps cleared" points the model at something that is always zero.
#     An earlier version of this prompt did exactly that.
#   * Choosing a node CLOSES the others on that layer, forever.

GAME_RULES = """You are playing Pokelike, a Pokemon roguelike.

YOUR GOAL: earn as many gym badges as you can before your team is wiped out.
Badges measure how far you got. A run ends when every Pokemon has fainted.

HOW A TURN WORKS
- The map is a layered graph running top to bottom, with a boss at the bottom.
- You pick one node from the legal ones. The moment you pick, every other node on
  that layer CLOSES FOREVER. The choice is irreversible and it also decides which
  nodes you will be able to reach next.
- Battles resolve themselves. You never choose moves. What you decide is where to
  go, who to catch, which item to take and who to give it to.
- Your team holds up to 6 Pokemon.

NODE TYPES
  o catch        adds a Pokemon to your team
  x wild fight   one wild Pokemon, gives experience
  T trainer      1 Pokemon on map 0, 2 on maps 1-2, 3 from map 3 onwards
  i item         an item to equip or keep
  + pokecenter   restores HP
  ? unknown      only revealed when you enter it
  $ trade        M move tutor    S shop    B boss

WHAT ACTUALLY KILLS RUNS
Losing Pokemon. Every faint is permanent for that run, and once the team is empty
it is over, no matter how well you were doing.
"""

CLOSING = "\nThink briefly, then call `play` with your chosen index. Always call `play`."


# ---------------------------------------------------------------------- tools
#
# Shared by default for the same reason the rules are: a model given a tool
# another model was not is not being compared, it is being helped.
#
# A bot may still add its own, or replace these outright -- see `tools()` and
# `run_tool()` on LLMBot. What it may not do is hide that it did: the tool names
# go into every result and a bot whose set differs from the shared one is
# marked in the standings, so its row is read as the different question it is.

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

    A bad token, a model name the endpoint does not serve, a URL that is not an
    OpenAI-compatible API. Falling back on these would play a whole run on the
    backup heuristic and report it as an LLM result — which, in a benchmark, puts
    an entry on the leaderboard labelled `llm` that no model ever played.
    So these stop the run instead.
    """


class LLMBudgetError(LLMError):
    """The run asked for more tokens than the bot allowed itself.

    Only raised when a bot sets `TOKEN_BUDGET`. A model that thinks ten times
    longer than the others is not straightforwardly better than them, and over
    fifty runs the difference is money, so a bot may declare a ceiling and be
    held to it rather than discovering the bill afterwards.
    """


# ------------------------------------------------------------------------ bot


class LLMBot(Bot):
    """A bot that asks a model what to do, one call per turn.

    Subclass it and set `PROMPT`. Everything else has a working default.

    | attribute      | what it decides                                        |
    |----------------|--------------------------------------------------------|
    | `PROMPT`       | the system prompt: **this is your submission**          |
    | `MODEL`        | model id, or None to take `$MODEL_ID`                   |
    | `TEMPERATURE`  | sampling                                               |
    | `MAX_TOKENS`   | ceiling on one answer                                  |
    | `MAX_ROUNDS`   | tool rounds before the turn is given up on             |
    | `MEMORY`       | how many past turns are shown back to the model        |
    | `TOKEN_BUDGET` | tokens per run, 0 for no ceiling                       |
    | `EXTRA_TOOLS`  | tools of your own, on top of the shared four            |
    | `STATE_VIEW`   | **what the model reads each turn**                      |

    `STATE_VIEW` is the one to think hardest about, because it decides what the
    model is looking at rather than what it is told to do:

    | value | what the model gets | roughly |
    |---|---|--:|
    | `"screen"` | the ASCII view a person sees. The default | 880 chars |
    | `"json"` | the whole state dict, compact JSON | 5900 chars |
    | `"both"` | the view, then the dict under it | 6800 chars |
    | `["team", "actions"]` | just those keys, as JSON | varies |

    Six times the tokens is the price of `"json"`, and it is not only money:
    filling the context with a map the turn does not need takes room from the
    reasoning it was about to do. The default drops real things -- the engine's
    type/item table, the map edges, raw base stats -- because it renders what a
    person would look at, not everything that is true. Which of those matters is
    an experiment, which is why this is a knob and not our decision.

    `view(state)` is the escape hatch when none of the four fit. Override it and
    return whatever string you like; the journal and the "pick an index"
    instruction are added around it by the harness, so you cannot break them by
    forgetting them.

    To give the model something the shared tools do not offer, declare it in
    `EXTRA_TOOLS` and answer it in `run_tool`:

        class MyBot(LLMBot):
            EXTRA_TOOLS = [{
                "type": "function",
                "function": {
                    "name": "bag",
                    "description": "What you are carrying.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }]

            def run_tool(self, name, args, state):
                if name == "bag":
                    return ", ".join(state.get("bag") or []) or "(empty)"
                return super().run_tool(name, args, state)

    Replacing the shared set entirely is `tools()`. Both are allowed and both
    are recorded: a bot with its own tools is answering a different question
    from one without, and the standings say so rather than ranking them as
    though they had been asked the same thing.

    On `MODEL`: pin it in the bot file if you want a leaderboard row that means
    one specific model — the id is not a secret, and pinning it puts it inside
    the fingerprint, so swapping the model shows as a changed bot. Leave it None
    and the bot plays whatever `$MODEL_ID` names, which is what you want while
    experimenting and what the four prompt bots shipped in `bots/` do.
    """

    name = "llm"

    HARNESS = HARNESS
    PROMPT = GAME_RULES + CLOSING
    MODEL: str | None = None
    TEMPERATURE = 0.6
    MAX_TOKENS = 1500
    MAX_ROUNDS = 4
    MEMORY = 6
    TOKEN_BUDGET = 0
    # Attempts after the first, for failures that are worth trying again: rate
    # limits and the 5xx family. Not a nicety once runs go in parallel -- a 429
    # would otherwise be counted as a turn the model failed to answer, which is
    # exactly the column that decides whether a benchmark row means anything.
    RETRIES = 4
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
                "FW_ENDPOINT and FW_TOKEN are required, from the environment or "
                "from the command line\n"
                '  export FW_ENDPOINT="https://..."   # base URL, no /v1\n'
                '  export FW_TOKEN="..."\n'
                "or, without exporting anything:\n"
                "  --endpoint https://... --api-key sk-...\n"
                "  --endpoint https://... --api-key @path/to/key   # keeps it out of `ps`"
            )
        if not self.model:
            raise LLMConfigError(
                f"{type(self).__name__} pins no MODEL, so a model id is required\n"
                '  export MODEL_ID="gpt-4o-mini"      or      --model gpt-4o-mini'
            )

        # Per-instance copies of the class settings, so a caller can override one
        # without editing the bot: create("llm-survivor") uses the declared ones,
        # LLMBot(temperature=0) in a notebook does not.
        self.system = overrides.pop("prompt", None) or self.PROMPT
        self.temperature = overrides.pop("temperature", self.TEMPERATURE)
        self.max_tokens = overrides.pop("max_tokens", self.MAX_TOKENS)
        self.max_rounds = overrides.pop("max_rounds", self.MAX_ROUNDS)
        self.memory = overrides.pop("memory", self.MEMORY)
        # Settable here as well as on the class so an experiment can put four
        # views on the same seeds without four bot folders. A SUBMISSION should
        # still declare it on the class: the fingerprint covers the class, and a
        # row whose view was chosen by the caller does not say what it played.
        self.state_view = overrides.pop("view", None) or self.STATE_VIEW
        self.token_budget = overrides.pop("token_budget", self.TOKEN_BUDGET)
        if overrides:
            raise TypeError(f"unknown settings: {', '.join(sorted(overrides))}")
        self.verbose = verbose or bool(os.environ.get("POKELIKE_VERBOSE"))

        # Checked once, here, rather than discovered fifty runs in. Without
        # `play` there is no way for the model to end a turn, so every turn
        # exhausts its rounds and falls back -- a whole benchmark of our backup
        # heuristic, filed under the model's name, with nothing that looks wrong
        # until you read fallback_rate.
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
        self._last_why = ""
        # The turn decided in `rearrange`, waiting for `choose` to collect it.
        self._pending: tuple[int | None, int | None, str] | None = None

    # ------------------------------------------------------------------ hooks

    def on_start(self, seed: int) -> None:
        self.seed = seed
        self.journal = []
        self._pending = None
        self.calls = self.turns = self.tokens_used = self.fallbacks = 0
        self.tokens_in = self.tokens_out = self.retries = 0
        self._last_why = ""

    def notes(self) -> dict[str, Any]:
        """Ends up in the run registry, and in the result a benchmark records.

        `fallback_rate` is the honest column of an LLM benchmark. Every fallback
        is a turn the model did not decide, played by the backup heuristic under
        the model's name — so a row with a high one is measuring our heuristic,
        not the model, and should be read as a broken run rather than a bad one.
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
            # Transient failures that were retried rather than counted
            # against the model. High means the provider was struggling.
            "retries": self.retries,
            "fallbacks": self.fallbacks,
            "fallback_rate": round(self.fallbacks / self.turns, 3) if self.turns else 0.0,
            "temperature": self.temperature,
            # False means this bot answers a different question from the others:
            # it gave the model tools they did not have, or took some away.
            "stock_tools": self.tool_names() == _STOCK_TOOL_NAMES,
            # What the model was looking at. Two rows with different views are
            # not answering the same question, any more than two with different
            # tools are.
            "state_view": self.view_name(),
            "reproducible": False,
        }

    def tool_names(self) -> list[str]:
        return [t["function"]["name"] for t in self.tools()]

    def artifacts(self) -> list:
        """What a submission of this bot carries.

        The prompt and the model reference, never the key. An LLM result cannot
        be reproduced exactly — providers change models behind a fixed name and
        sampling is stochastic — so the least we can do is record precisely what
        was asked of which model, under which harness.
        """
        from pokelike.leaderboard import Artifact

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

    def explain(self) -> str:
        return self._last_why

    def rearrange(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Who leads, decided in the SAME model call as the move.

        The run loop asks for this before `choose`, so the whole turn is thought
        about once: `_agentic_round` runs here, the chosen action is cached, and
        `choose` returns it without a second request. One HTTP call per turn —
        the model simply gets one more tool.

        Offered only on the map screen. Elsewhere the options ARE the team (the
        swap screen, the equip modal), so reordering underneath would change what
        an index means between deciding and playing.
        """
        self._pending = None
        if state.get("screen") != "map-screen" or not state.get("can_reorder"):
            return None
        try:
            index, why, lead = self._agentic_round(state, allow_lead=True)
        except LLMConfigError:
            raise
        except Exception:  # noqa: BLE001 — handled again, and counted, in choose
            return None
        team = state.get("team") or []
        if lead is None or not 0 < lead < len(team):
            self._pending = (state.get("steps"), index, why)
            return None
        # Carried into the turn's explanation rather than set here: `choose`
        # overwrites `_last_why` with the move reason, so a lead decision set
        # here was performed and then never shown.
        why = f"lead {team[lead]['name']} | {why}"
        self._pending = (state.get("steps"), index, why)
        return (0, lead)

    def choose(self, state: dict[str, Any]) -> int:
        self.turns += 1
        n = len(state["actions"])
        # Already decided in rearrange, this same turn. `steps` guards it: a
        # cached index must never be replayed against a different turn.
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
        except Exception as e:  # noqa: BLE001 — a transient failure must not end the run
            return self._fall_back(state, f"{type(e).__name__}: {e}"[:80])

        if not isinstance(index, int) or not 0 <= index < n:
            return self._fall_back(state, f"model returned index {index}")
        return self._commit(state, index, why)

    def _commit(self, state: dict[str, Any], index: int, why: str) -> int:
        self._last_why = why
        self.journal.append(self._journal_entry(state, index, why))
        self.journal = self.journal[-self.memory:]
        if self.verbose:
            print(f"   [llm] -> [{index}] {why[:100]}")
        return index

    def _journal_entry(self, state: dict[str, Any], index: int, why: str) -> str:
        """One past turn, with the action separated from the talk about it.

        This used to record `why` alone, the model's own sentence, under a heading
        that read YOUR RECENT MOVES. So a model was handed its own guesses back as
        a record of events: "a second Pokemon matters more than one more fight
        this early" is a plan, and after a turn it reads as a thing that happened.
        Nothing in the loop had told it otherwise, and there was no way for it to
        tell the two apart.

        What was actually done comes from `state["actions"][index]`, which is the
        harness's own data, and the sentence is kept underneath and labelled. The
        reasoning is worth keeping: it is how a model notices it has been trying
        the same idea for five turns. It is just not evidence.
        """
        actions = state.get("actions") or []
        act = actions[index] if 0 <= index < len(actions) else {}
        if act.get("kind") == "node":
            did = f"node {act.get('id', '?')} ({act.get('node', 'node')})"
        else:
            did = str(act.get("label") or act.get("id") or "action")
        said = " ".join(str(why or "").split())[:200]
        return (f"step {state.get('steps')}: [{index}] {did}\n"
                f"    it said: {said or '(nothing)'}")

    def _fall_back(self, state: dict[str, Any], reason: str) -> int:
        self.fallbacks += 1
        self._last_why = f"(fell back: {reason})"
        if self.verbose:
            print(f"   [llm] fallback: {reason}")
        return self._fallback(state)

    def _fallback(self, state: dict[str, Any]) -> int:
        """Backup choice when the model does not answer or gets it wrong.

        Not random: it prefers what keeps the team alive — heal first if someone
        is hurt, otherwise widen the team. Override it if your bot would rather
        fail differently, but count on it being used: over fifty runs, something
        times out.
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
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self._situation(state)},
        ]

        for _ in range(self.max_rounds):
            msg = self._call(messages)
            calls = msg.get("tool_calls") or []
            if not calls:
                # No tool: maybe it wrote the index out in prose.
                index = self._index_from_text(msg.get("content") or "", len(state["actions"]))
                if index is not None:
                    return index, "(read from prose)", lead
                raise LLMError("the model called no tool")

            messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": calls,
            })

            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}

                if name == "play":
                    return args.get("index"), str(args.get("why", "")), lead

                if name == "set_lead":
                    # Recorded, not applied here: the bot has no handle on the
                    # game, and the run loop is what performs the swap. Kept even
                    # when not allowed, so the model gets told why rather than
                    # silently ignored.
                    want = args.get("index")
                    if allow_lead and isinstance(want, int):
                        lead = want
                        reply = f"ok, slot {want} will lead. Now call play()."
                    else:
                        reply = ("not available on this screen: the options here are "
                                 "your team, so reordering would change what an index "
                                 "means. Call play().")
                    messages.append({
                        "role": "tool", "tool_call_id": c["id"], "content": reply,
                    })
                    continue

                messages.append({
                    "role": "tool",
                    "tool_call_id": c["id"],
                    "content": self.run_tool(name, args, state),
                })

        raise LLMError(f"no call to play() within {self.max_rounds} rounds")

    # ------------------------------------------------------------------ tools

    def tools(self) -> list[dict[str, Any]]:
        """The tools this bot offers the model, in OpenAI function-calling form.

        The shared four plus whatever `EXTRA_TOOLS` declares. Override to drop
        or replace them — but `play` has to survive: it is how a turn ends, and
        a model with no way to end the turn falls back on every single one.
        """
        return [*TOOLS, *self.EXTRA_TOOLS]

    def run_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call. Whatever this returns is shown to the model.

        Override for your own tools and call `super()` for the shared ones. An
        unknown name gets a message rather than an exception: a model that
        invents a tool should be told so and allowed to carry on, not have the
        turn thrown away and played by the fallback.
        """
        if name == "team_details":
            return render.team_view(state.get("team")) or "(empty team)"
        if name == "what_lies_ahead":
            return self._exits(state)
        return f"unknown tool: {name}"

    # ---------------------------------------------------------------- context

    def view(self, state: dict[str, Any]) -> str:
        """What the model reads each turn. THE hook for changing that.

        Reads `STATE_VIEW` (or whatever was passed as `view=`). Override it
        outright for anything the four settings do not cover -- the harness adds
        the journal and the instruction line around whatever this returns, so
        replacing it wholesale cannot silently cost the bot its memory or leave
        the model without the range of legal indices. That was the shape of the
        old private `_situation`, where the thing you wanted to change and the
        plumbing you must not break lived in one method.
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
                # Not an error: a key can be absent on one screen and present on
                # the next -- `map` is gone during a battle. Saying so beats a
                # view that quietly shrinks and a run that gets worse for reasons
                # nobody can see.
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
        if type(self).view is not LLMBot.view:
            return "custom"
        return self.state_view if isinstance(self.state_view, str) else \
            "keys:" + ",".join(self.state_view)

    def _situation(self, state: dict[str, Any]) -> str:
        """The whole user message: the view, plus what the harness owns.

        Deliberately not the hook. The journal is what stops a bot walking the
        same loop forever, and the instruction line is what tells the model how
        many options there are -- neither is a choice a bot should be able to
        drop by accident while changing something else.

        The journal separates what was done from what was said about it, and the
        heading says so. It used to read YOUR RECENT MOVES over a list of the
        model's own sentences, which is the one arrangement that turns a guess
        into a fact by doing nothing at all.
        """
        parts = [self.view(state)]
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

    def _call(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
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
            # Best effort only. Providers that honour it get closer to repeatable
            # runs; most ignore it, and none of them promise it. Nothing here
            # depends on it working — see `reproducible: False` in the artifacts.
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
        # Retried, with backoff, for the failures that are transient. A rate limit
        # is not the model failing to answer: counted as a fallback it would show
        # up as the model being bad at the game, and it is the first thing that
        # happens when runs go in parallel.
        #
        # Auth and model-not-found are NOT retried -- they fail identically
        # forever, so trying again just wastes the run more slowly.
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
                        f"token.\n  Check FW_TOKEN — a placeholder left in place looks "
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
        # Split, not just the total. Input and output are priced differently --
        # output several times higher -- so a single total cannot be turned into
        # money afterwards, and a model that thinks in long answers costs quite
        # unlike one that reads a long prompt. Kept as counts and nothing else:
        # prices change, and a measurement should not go stale because a provider
        # ran a promotion. Cost is a function of these two numbers applied later.
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
