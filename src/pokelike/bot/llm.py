"""The harness every LLM bot shares.

An LLM bot is a prompt and a model. Everything around them — how the state
becomes text, which tools exist, how many rounds of thinking are allowed, what
happens when a call fails — is machinery, and it lives here rather than in each
bot, for one reason: **a benchmark of models has to hold the harness still.**
Two bots with different loops are not two models being compared, they are two
harnesses, and the model is the smaller half of the difference.

So a bot built on this is short: a prompt in an `LLMConfig`.

    from pokelike.bot.llm import LLMBot, LLMConfig, GAME_RULES

    class SurvivorBot(LLMBot):
        name = "llm-survivor"
        config = LLMConfig(
            prompt=GAME_RULES + "Heal before it is urgent. Always call play().",
        )

Credentials never appear in a bot file. They come from the environment, always:

    export FW_ENDPOINT="https://..."     # base URL; /v1/chat/completions is added
    export FW_TOKEN="..."
    export MODEL_ID="..."                # unless the config pins `model` itself
    uv run pokelike bot run --bot llm-survivor --runs 3

**This file is shared, which is the thing to be careful about.** The whole point
of a bot being self-contained is that improving our code cannot silently change
what a past measurement meant. Code in here is the exception: it is shared on
purpose, so editing it *does* reach every LLM bot ever measured. `harness_version`
is how that stays honest — it is written into every result, and a result recorded
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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
# `answer_tool()` on LLMBot. What it may not do is hide that it did: the tool
# names go into every result and a bot whose set differs from the shared one is
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

    Only raised when a config sets `token_budget`. A model that thinks ten times
    longer than the others is not straightforwardly better than them, and over
    fifty runs the difference is money, so a bot may declare a ceiling and be
    held to it rather than discovering the bill afterwards.
    """


# --------------------------------------------------------------------- config

StateView = Literal["screen", "json", "both"] | list[str]


class LLMConfig(BaseModel):
    """Every knob an LLM bot can turn, in one validated place.

    A bot sets the ones it cares about and inherits the rest:

        config = LLMConfig(prompt=GAME_RULES + "...", temperature=0.3)

    `extra="forbid"` means a typo in a field name is caught the moment the bot is
    built, not fifty runs later. Credentials are deliberately NOT here: the
    endpoint and token come from the environment or the command line, because
    this object is fingerprinted and written into `result.json`.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str = GAME_RULES + CLOSING          # the system prompt: the submission
    model: str | None = None                    # pin an id, or None to take $MODEL_ID
    temperature: float = 0.6
    max_tokens: int = 1500
    max_rounds: int = 4                          # tool rounds before the turn is given up
    memory: int = 6                              # past turns replayed; -1 = keep all
    token_budget: int = 0                        # per-run cap, 0 = none
    retries: int = 4                             # attempts on a transient HTTP failure
    extra_tools: list[dict[str, Any]] = Field(default_factory=list)
    state_view: StateView = "screen"             # what the model reads each turn


# ------------------------------------------------------------------------ bot


class LLMBot(Bot):
    """A bot that asks a model what to do, one call per turn.

    Subclass it and set `config` (at least a `prompt`). Everything else has a
    working default.

    `state_view` is the field to think hardest about, because it decides what the
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
    person would look at, not everything that is true.

    `render_state(state)` is the escape hatch when none of the four fit. Override
    it and return whatever string you like; the journal and the "pick an index"
    instruction are added around it by the harness, so you cannot break them by
    forgetting them.

    To give the model something the shared tools do not offer, declare it in
    `config.extra_tools` and answer it in `answer_tool`. Replacing the shared set
    entirely is `tools()`. Both are allowed and both are recorded: a bot with its
    own tools is answering a different question from one without, and the
    standings say so rather than ranking them as though they were the same.

    On `config.model`: pin it if you want a leaderboard row that means one
    specific model — the id is not a secret, and pinning it puts it inside the
    fingerprint, so swapping the model shows as a changed bot. Leave it None and
    the bot plays whatever `$MODEL_ID` names.
    """

    name = "llm"

    # The generation of the shared loop, written into every result. Not in the
    # config because it is not a knob a bot turns: it is a fact about this file.
    harness_version = HARNESS

    # The default config. A subclass overrides it with its own LLMConfig(...).
    config: LLMConfig = LLMConfig()

    def __init__(self, seed: int = 0, endpoint: str | None = None,
                 token: str | None = None, model: str | None = None,
                 config: LLMConfig | None = None, verbose: bool = False,
                 **overrides: Any) -> None:
        super().__init__(seed=seed)
        self.endpoint = (endpoint or os.environ.get("FW_ENDPOINT", "")).rstrip("/")
        self.token = token or os.environ.get("FW_TOKEN", "")

        # Per-instance config: start from the passed or class-declared config and
        # apply any keyword overrides, so `LLMBot(temperature=0)` works in a
        # notebook without a bot file. `view=` is accepted as a friendly alias
        # for `state_view`. A submission should still declare its knobs on the
        # class: the fingerprint covers the class, and a row whose view was chosen
        # by the caller does not say what it played.
        if "view" in overrides:
            overrides["state_view"] = overrides.pop("view")
        base = config or type(self).config
        # Rebuilt through the model (not model_copy) so overrides are validated
        # and an unknown one is rejected here rather than silently ignored.
        self.cfg = LLMConfig(**{**base.model_dump(), **overrides})

        self.model = model or self.cfg.model or os.environ.get("MODEL_ID", "")
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
                f"{type(self).__name__} pins no model, so a model id is required\n"
                '  export MODEL_ID="gpt-4o-mini"      or      --model gpt-4o-mini'
            )
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
        self.retry_count = 0
        self.fallbacks = 0
        self.journal: list[str] = []
        self._last_why = ""
        # The turn decided in `reorder`, waiting for `act` to collect it.
        self._pending: tuple[int | None, int | None, str] | None = None

    # ------------------------------------------------------------------ hooks

    def reset(self, seed: int) -> None:
        self.seed = seed
        self.journal = []
        self._pending = None
        self.calls = self.turns = self.tokens_used = self.fallbacks = 0
        self.tokens_in = self.tokens_out = self.retry_count = 0
        self._last_why = ""

    def metadata(self) -> dict[str, Any]:
        """Ends up in the run registry, and in the result a benchmark records.

        `fallback_rate` is the honest column of an LLM benchmark. Every fallback
        is a turn the model did not decide, played by the backup heuristic under
        the model's name — so a row with a high one is measuring our heuristic,
        not the model, and should be read as a broken run rather than a bad one.
        """
        return {
            "model": self.model,
            "harness": self.harness_version,
            "bot": type(self).__name__,
            "calls": self.calls,
            "turns": self.turns,
            "tokens": self.tokens_used,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            # Transient failures that were retried rather than counted
            # against the model. High means the provider was struggling.
            "retries": self.retry_count,
            "fallbacks": self.fallbacks,
            "fallback_rate": round(self.fallbacks / self.turns, 3) if self.turns else 0.0,
            "temperature": self.cfg.temperature,
            # False means this bot answers a different question from the others:
            # it gave the model tools they did not have, or took some away.
            "stock_tools": self.tool_names() == _STOCK_TOOL_NAMES,
            # What the model was looking at. Two rows with different views are
            # not answering the same question, any more than two with different
            # tools are.
            "state_view": self._state_view_label(),
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
        from pokelike.arena.leaderboard import Artifact

        return [
            Artifact(
                name="prompt.md",
                kind="prompt",
                description=f"system prompt, {type(self).__name__}",
                text=self.cfg.prompt,
            ),
            Artifact(
                name="model.json",
                kind="model-ref",
                description="which model answered, and how it was asked",
                data={
                    "model": self.model,
                    "pinned": type(self).config.model is not None,
                    "harness": self.harness_version,
                    "temperature": self.cfg.temperature,
                    "max_tokens": self.cfg.max_tokens,
                    "max_rounds": self.cfg.max_rounds,
                    "memory": self.cfg.memory,
                    "token_budget": self.cfg.token_budget,
                    "tools": self.tool_names(),
                    "stock_tools": self.tool_names() == _STOCK_TOOL_NAMES,
                    "state_view": self._state_view_label(),
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
        """Who leads, decided in the SAME model call as the move.

        The run loop asks for this before `act`, so the whole turn is thought
        about once: `_run_turn` runs here, the chosen action is cached, and `act`
        returns it without a second request. One HTTP call per turn — the model
        simply gets one more tool.

        Offered only on the map screen. Elsewhere the options ARE the team (the
        swap screen, the equip modal), so reordering underneath would change what
        an index means between deciding and playing.
        """
        self._pending = None
        if state.get("screen") != "map-screen" or not state.get("can_reorder"):
            return None
        try:
            index, why, lead = self._run_turn(state, allow_lead=True)
        except LLMConfigError:
            raise
        except Exception as e:  # noqa: BLE001
            # call_model already retried transient failures, so this turn's model
            # budget is spent. Record the failure against this step so `act` falls
            # back instead of paying for a SECOND full turn (the old code dropped
            # it silently and act re-ran the whole call).
            self._pending = (state.get("steps"), None, f"{type(e).__name__}: {e}"[:80])
            return None
        team = state.get("team") or []
        if lead is None or not 0 < lead < len(team):
            self._pending = (state.get("steps"), index, why)
            return None
        # Carried into the turn's explanation rather than set here: `act`
        # overwrites `_last_why` with the move reason, so a lead decision set
        # here was performed and then never shown.
        why = f"lead {team[lead]['name']} | {why}"
        self._pending = (state.get("steps"), index, why)
        return (0, lead)

    def act(self, state: dict[str, Any]) -> int:
        self.turns += 1
        n = len(state["actions"])
        # Already decided in reorder, this same turn. `steps` guards it: a
        # cached index must never be replayed against a different turn.
        if self._pending and self._pending[0] == state.get("steps"):
            _, index, why = self._pending
            self._pending = None
            if isinstance(index, int) and 0 <= index < n:
                return self._cache_decision(state, index, why)
            # reorder already ran (and spent) this turn's model call. If it left
            # no usable move -- a transient failure, or a play with no valid index
            # -- fall back here rather than calling the model a second time.
            return self._run_fallback(state, why or f"model returned index {index}")
        try:
            index, why, _ = self._run_turn(state)
        except (LLMConfigError, LLMBudgetError):
            # Not recoverable: every later call fails identically, or the run has
            # spent what it was allowed. Better to stop than to quietly hand the
            # rest of the run to the backup heuristic and file it as an LLM run.
            raise
        except Exception as e:  # noqa: BLE001 — a transient failure must not end the run
            return self._run_fallback(state, f"{type(e).__name__}: {e}"[:80])

        if not isinstance(index, int) or not 0 <= index < n:
            return self._run_fallback(state, f"model returned index {index}")
        return self._cache_decision(state, index, why)

    def _cache_decision(self, state: dict[str, Any], index: int, why: str) -> int:
        self._last_why = why
        self.journal.append(self._journal_entry(state, index, why))
        if self.cfg.memory >= 0:
            self.journal = self.journal[-self.cfg.memory:]
        # memory < 0 (i.e. -1) keeps every turn: an unbounded, append-only memory.
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
        chosen = actions[index] if 0 <= index < len(actions) else {}
        if chosen.get("kind") == "node":
            did = f"node {chosen.get('id', '?')} ({chosen.get('node', 'node')})"
        else:
            did = str(chosen.get("label") or chosen.get("id") or "action")
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

    def _run_turn(self, state: dict[str, Any],
                  allow_lead: bool = False) -> tuple[int, str, int | None]:
        """One turn of thinking. Returns (action index, reason, lead or None)."""
        lead: int | None = None
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.cfg.prompt},
            {"role": "user", "content": self._build_user_message(state)},
        ]

        for _ in range(self.cfg.max_rounds):
            msg = self.call_model(messages)
            calls = msg.get("tool_calls") or []
            if not calls:
                # No tool: maybe it wrote the index out in prose.
                index = self._parse_index(msg.get("content") or "", len(state["actions"]))
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
                    return self._as_index(args.get("index")), str(args.get("why", "")), lead

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
                    "content": self.answer_tool(name, args, state),
                })

        raise LLMError(f"no call to play() within {self.cfg.max_rounds} rounds")

    # ------------------------------------------------------------------ tools

    def tools(self) -> list[dict[str, Any]]:
        """The tools this bot offers the model, in OpenAI function-calling form.

        The shared four plus whatever `config.extra_tools` declares. Override to
        drop or replace them — but `play` has to survive: it is how a turn ends,
        and a model with no way to end the turn falls back on every single one.
        """
        # `self.cfg` on a built bot, the class default when introspected unbuilt.
        cfg = getattr(self, "cfg", None) or self.config
        return [*TOOLS, *cfg.extra_tools]

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call. Whatever this returns is shown to the model.

        Override for your own tools and call `super()` for the shared ones. An
        unknown name gets a message rather than an exception: a model that
        invents a tool should be told so and allowed to carry on, not have the
        turn thrown away and played by the fallback.
        """
        if name == "team_details":
            return render.team_view(state.get("team")) or "(empty team)"
        if name == "what_lies_ahead":
            return self._exits_text(state)
        return f"unknown tool: {name}"

    # ---------------------------------------------------------------- context

    def render_state(self, state: dict[str, Any]) -> str:
        """What the model reads each turn. THE hook for changing that.

        Reads `config.state_view` (or whatever was passed as `view=`). Override
        it outright for anything the four settings do not cover -- the harness
        adds the journal and the instruction line around whatever this returns,
        so replacing it wholesale cannot silently cost the bot its memory or
        leave the model without the range of legal indices.
        """
        spec = self.cfg.state_view
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
                    print(f"   [llm] state_view: no {', '.join(missing)} on this screen")
            return json.dumps({k: state[k] for k in spec if k in state},
                              separators=(",", ":"))
        raise LLMConfigError(
            f"state_view is {spec!r}. Use 'screen', 'json', 'both', a list of "
            f"state keys, or override render_state(state) yourself."
        )

    def _state_view_label(self) -> str:
        """What to record: the setting, or 'custom' if `render_state` was replaced."""
        if type(self).render_state is not LLMBot.render_state:
            return "custom"
        spec = self.cfg.state_view
        return spec if isinstance(spec, str) else "keys:" + ",".join(spec)

    def _build_user_message(self, state: dict[str, Any]) -> str:
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
        parts = [self.render_state(state)]
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

    def _exits_text(self, state: dict[str, Any]) -> str:
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
        """The whole of the network. Override this for a model that is not an
        OpenAI-compatible HTTP endpoint (a local checkpoint, a client library),
        and the loop, the tools, the journal and the fallback policy above it
        keep working unchanged. Return the OpenAI-shaped `message` dict, keep the
        token counters up to date, and raise `LLMConfigError` for anything that
        would fail identically forever, `LLMError` for anything transient.
        """
        if self.cfg.token_budget and self.tokens_used >= self.cfg.token_budget:
            raise LLMBudgetError(
                f"run spent {self.tokens_used} tokens, budget is {self.cfg.token_budget}"
            )
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": self.tools(),
            "tool_choice": "auto",
            "max_tokens": self.cfg.max_tokens,
            "temperature": self.cfg.temperature,
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
        for attempt in range(self.cfg.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    answer = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode("utf-8", "replace")
                if e.code in (401, 403):
                    raise LLMConfigError(
                        f"HTTP {e.code} from {self.endpoint}: the endpoint rejected the "
                        f"token.\n  Check FW_TOKEN: a placeholder left in place looks "
                        f"exactly like this.\n  {detail}"
                    ) from e
                if e.code == 404:
                    raise LLMConfigError(
                        f"HTTP 404 from {self.endpoint}/v1/chat/completions.\n"
                        f"  Either the endpoint is not an OpenAI-compatible API, or it "
                        f"does not serve MODEL_ID={self.model!r}.\n  {detail}"
                    ) from e
                if e.code in (408, 409, 425, 429, 500, 502, 503, 504) \
                        and attempt < self.cfg.retries:
                    self.retry_count += 1
                    time.sleep(min(2 ** attempt, 30) + random.random())
                    continue
                raise LLMError(f"HTTP {e.code}: {detail}") from e
            except Exception as e:  # network, timeout, malformed JSON
                if attempt < self.cfg.retries:
                    self.retry_count += 1
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
    def _as_index(v: Any) -> int | None:
        """A tool argument as an int, or None. Models often send `"2"` (a string)
        instead of `2`; treat a plain integer string as the integer it obviously
        is, rather than throwing the decision away as malformed."""
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().lstrip("+-").isdigit():
            return int(v.strip())
        return None

    @staticmethod
    def _parse_index(text: str, n: int) -> int | None:
        """Last resort: fish a valid index out of a prose answer.

        The LAST valid number, not the first: a model states its reasoning before
        its conclusion ("option 0 looks weak, so I'll take 2"), so the answer is
        the last index it names, not the first it mentions.
        """
        import re

        valid = [v for v in (int(m.group(1)) for m in re.finditer(r"\[?(\d+)\]?", text))
                 if 0 <= v < n]
        return valid[-1] if valid else None
