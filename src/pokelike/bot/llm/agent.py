"""The LLMBot class and the one-call-per-turn decision loop.

This file is shared on purpose, so editing it reaches every LLM bot. The
`harness_version` constant is written into every result and bumped whenever a
change here could move a decision.
"""

from __future__ import annotations

import os
from typing import Any

from pokelike.bot.base import Bot
from pokelike.core import render

from .config import LLMBudgetError, LLMConfig, LLMConfigError, LLMError
from .fallback import _as_index, _parse_index, fallback_move_default
from .journal import build_user_message, journal_entry, trim_journal
from .loop import _LoopExhausted, run_turn
from .notebook import Notebook
from .prompt import exits_text, render_state_default, state_view_label
from .record import build_artifacts, build_metadata
from .tools import CLOSING, GAME_RULES, TOOLS, _STOCK_TOOL_NAMES, build_tools
from .transport import call_model_http

# Generation of the shared loop. Written into every result; a row measured under
# a different number is marked as such rather than ranked as if it were the same.
#   1  agentic loop with team_details / what_lies_ahead / set_lead / play,
#      situation rendered by core.render.screen, prose index as last resort
#   2  opt-in notebook (remember/revise/forget), plan, and bag tools,
#      configurable per-note char limit, cross-run memory, plan_chars cap
HARNESS = 2


class LLMBot(Bot):
    """A bot that asks a model what to do, one call per turn.

    In: subclass it and set `config` (at least a `prompt`). Out: a bot that
    plays the game via an LLM endpoint, with tools, journal and fallback.
    """

    name = "llm"
    harness_version = HARNESS
    config: LLMConfig = LLMConfig(prompt=GAME_RULES + CLOSING)

    def __init__(self, seed: int = 0, endpoint: str | None = None,
                 token: str | None = None, model: str | None = None,
                 config: LLMConfig | None = None, verbose: bool = False,
                 **overrides: Any) -> None:
        """Builds the bot and validates credentials and tool configuration.

        In: endpoint/token/model from args or env, optional config overrides.
        Out: a ready bot, or LLMConfigError if credentials or tools are wrong.
        """
        super().__init__(seed=seed)
        self.endpoint = (endpoint or os.environ.get("FW_ENDPOINT", "")).rstrip("/")
        self.token = token or os.environ.get("FW_TOKEN", "")
        if "view" in overrides:
            overrides["state_view"] = overrides.pop("view")
        base = config or type(self).config
        self.cfg = LLMConfig(**{**base.model_dump(), **overrides})
        self.model = model or self.cfg.model or os.environ.get("MODEL_ID", "")
        if not self.endpoint or not self.token:
            raise LLMConfigError(
                "FW_ENDPOINT and FW_TOKEN are required, from a .env file, the "
                "environment, or the command line\n"
                "  .env at the repository root, which is gitignored and which the\n"
                "  container reads too. The easiest, and the key stays out of `ps`:\n"
                '    FW_ENDPOINT=https://...\n'
                '    FW_TOKEN=...\n'
                "or exported, which wins over the file:\n"
                '  export FW_ENDPOINT="https://..."   # base URL, no /v1\n'
                '  export FW_TOKEN="..."\n'
                "or on the command line, which wins over both:\n"
                "  --endpoint https://... --api-key sk-...\n"
                "  --endpoint https://... --api-key @path/to/key   # keeps it out of `ps`"
            )
        if not self.model:
            raise LLMConfigError(
                f"{type(self).__name__} pins no model, so a model id is required\n"
                '  export MODEL_ID="gpt-4o-mini"      or      --model gpt-4o-mini'
            )
        self.verbose = verbose or bool(os.environ.get("POKELIKE_VERBOSE"))
        # Notebook: only constructed when notes_cap > 0.
        self._notebook: Notebook | None = None
        if self.cfg.notes_cap > 0:
            self._notebook = Notebook(self.cfg.notes_cap, self.cfg.note_chars)
        # Plan: per-run route, only active when plan_chars > 0.
        self.plan: str = ""
        self._validate_tools()
        self._init_counters()

    def _validate_tools(self) -> None:
        """Checks that the tool set has `play` and no duplicates."""
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

    def _init_counters(self) -> None:
        """Zeroes all mutable per-run state."""
        self.calls = self.turns = self.tokens_used = 0
        self.tokens_in = self.tokens_out = self.retry_count = self.fallbacks = 0
        self.journal: list[str] = []
        self._last_why = ""
        self._tool_calls: list[dict[str, Any]] = []
        self._pending: tuple[int | None, int | None, str] | None = None
        # Scratchpad: the last N finished exchanges, carried verbatim.
        self._scratch: list[list[dict[str, Any]]] = []

    def reset(self, seed: int) -> None:
        """Resets all per-run state for a new game.

        In: the new seed. Out: nothing (mutates self).
        """
        self.seed = seed
        self.journal = []
        self._pending = None
        self.calls = self.turns = self.tokens_used = self.fallbacks = 0
        self.tokens_in = self.tokens_out = self.retry_count = 0
        self._last_why = ""
        self._tool_calls: list[dict[str, Any]] = []
        # Plan and scratchpad are per-run: the plan describes a route through
        # THIS map, and the scratchpad is this episode's reasoning.
        self.plan = ""
        self._scratch: list[list[dict[str, Any]]] = []
        # Notebook survives reset only when cross_run_memory is on.
        if self._notebook and not self.cfg.cross_run_memory:
            self._notebook.clear()

    def metadata(self) -> dict[str, Any]:
        """Returns run metadata for the registry and benchmark results.

        In: nothing. Out: a dict with model, harness, token counts, fallback_rate,
        and view/tool configuration.
        """
        meta = build_metadata(
            model=self.model, harness_version=self.harness_version,
            bot_class_name=type(self).__name__,
            calls=self.calls, turns=self.turns, tokens_used=self.tokens_used,
            tokens_in=self.tokens_in, tokens_out=self.tokens_out,
            retry_count=self.retry_count, fallbacks=self.fallbacks,
            temperature=self.cfg.temperature,
            tool_names=self.tool_names(), state_view_label=self._state_view_label(),
        )
        # Report notebook/plan settings and current state so a result records
        # what the bot was allowed to do and what it held at the end.
        if self._notebook:
            meta["notes_cap"] = self.cfg.notes_cap
            meta["notes_kept"] = len(self._notebook.notes)
            meta["notebook"] = list(self._notebook.notes)
            meta["cross_run_memory"] = self.cfg.cross_run_memory
        if self.cfg.plan_chars > 0:
            meta["plan_chars"] = self.cfg.plan_chars
            meta["plan"] = self.plan
        if self.cfg.bag_tool:
            meta["bag_tool"] = True
        if self.cfg.scratch_turns > 0:
            meta["scratch_turns"] = self.cfg.scratch_turns
            meta["scratch_held"] = len(self._scratch)
        return meta

    def tool_names(self) -> list[str]:
        """Returns the names of all tools offered to the model."""
        return [t["function"]["name"] for t in self.tools()]

    def artifacts(self) -> list:
        """Returns what a submission of this bot carries for the record.

        In: nothing. Out: a list of Artifact objects (prompt and model reference).
        """
        return build_artifacts(
            bot_class_name=type(self).__name__, prompt=self.cfg.prompt,
            model=self.model, model_pinned=type(self).config.model is not None,
            harness_version=self.harness_version,
            temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens,
            max_rounds=self.cfg.max_rounds, memory=self.cfg.memory,
            token_budget=self.cfg.token_budget,
            tool_names=self.tool_names(), state_view_label=self._state_view_label(),
        )

    def reason(self) -> str:
        """Returns the explanation string for the last decision made."""
        return self._last_why

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Decides who leads, in the SAME model call as the move.

        In: the state dict. Out: a (from, to) swap pair, or None if no reorder.
        """
        # One HTTP call per turn: reorder runs first, caches the move for act.
        # Offered only on the map screen (elsewhere the options ARE the team).
        self._pending = None
        if state.get("screen") != "map-screen" or not state.get("can_reorder"):
            return None
        try:
            index, why, lead = self._run_turn(state, allow_lead=True)
        except LLMConfigError:
            raise
        except Exception as e:  # noqa: BLE001
            self._pending = (state.get("steps"), None, f"{type(e).__name__}: {e}"[:80])
            return None
        team = state.get("team") or []
        if lead is None or not 0 < lead < len(team):
            self._pending = (state.get("steps"), index, why)
            return None
        why = f"lead {team[lead]['name']} | {why}"
        self._pending = (state.get("steps"), index, why)
        return (0, lead)

    def act(self, state: dict[str, Any]) -> int:
        """Picks the move for this turn.

        In: the state dict the loop read from the game. Out: the index of the
        chosen action.
        """
        self.turns += 1
        n = len(state["actions"])
        if self._pending and self._pending[0] == state.get("steps"):
            _, index, why = self._pending
            self._pending = None
            if isinstance(index, int) and 0 <= index < n:
                return self._cache_decision(state, index, why)
            return self._run_fallback(state, why or f"model returned index {index}")
        try:
            index, why, _ = self._run_turn(state)
        except (LLMConfigError, LLMBudgetError):
            raise
        except Exception as e:  # noqa: BLE001
            return self._run_fallback(state, f"{type(e).__name__}: {e}"[:80])
        if not isinstance(index, int) or not 0 <= index < n:
            return self._run_fallback(state, f"model returned index {index}")
        return self._cache_decision(state, index, why)

    def _cache_decision(self, state: dict[str, Any], index: int, why: str) -> int:
        """Records a decision into the journal and returns the index.

        In: the state, chosen index, and reason. Out: the index (passed through).
        """
        self._last_why = why
        self.journal.append(journal_entry(state, index, why))
        self.journal = trim_journal(self.journal, self.cfg.memory)
        if self.verbose:
            print(f"   [llm] -> [{index}] {why[:100]}")
        return index

    def _run_fallback(self, state: dict[str, Any], reason: str) -> int:
        """Counts and executes a fallback when the model fails to decide.

        In: the state and a reason string. Out: the fallback action index.
        """
        self.fallbacks += 1
        self._last_why = f"(fell back: {reason})"
        if self.verbose:
            print(f"   [llm] fallback: {reason}")
        return self.fallback_move(state)

    def fallback_move(self, state: dict[str, Any]) -> int:
        """Backup choice when the model does not answer or gets it wrong.

        In: the state dict. Out: a safe action index (prefers healing, then
        widening the team).
        """
        return fallback_move_default(state)

    def _run_turn(self, state: dict[str, Any],
                  allow_lead: bool = False) -> tuple[int, str, int | None]:
        """Runs one turn of the agentic loop until play() is called.

        In: the state dict and whether set_lead is allowed. Out: a tuple of
        (action index, reason string, lead slot or None).
        """
        # Flatten the scratchpad into the history the loop inserts between the
        # system prompt and the fresh user message. When scratch_turns is 0 the
        # list is empty and the messages are exactly [system, user].
        history: list[dict[str, Any]] = [m for turn in self._scratch for m in turn]
        try:
            index, why, lead, this_turn = run_turn(
                state=state, allow_lead=allow_lead,
                system_prompt=self.cfg.prompt,
                user_message=self._build_user_message(state),
                max_rounds=self.cfg.max_rounds,
                call_model_fn=self.call_model, answer_tool_fn=self.answer_tool,
                parse_index_fn=self._parse_index, as_index_fn=self._as_index,
                record_call_fn=self._record_call,
                history=history if history else None,
            )
        except _LoopExhausted as exc:
            # Rounds exhausted: the turn is lost to the fallback, but its
            # exchange is kept anyway (a turn that ran out of ideas is exactly
            # what the next turn should see rather than repeat).
            self._remember_turn(exc.this_turn)
            raise LLMError(str(exc)) from exc
        self._remember_turn(this_turn)
        return index, why, lead

    def _remember_turn(self, turn: list[dict[str, Any]]) -> None:
        """Adds one finished exchange to the scratchpad, oldest dropped first.

        The screen the model was looking at is replaced by one line before the
        turn is kept: that line is most of what makes the scratchpad affordable.
        Measured on three seeds with the whole turn kept: 269k input tokens for
        ONE run against 41k (six and a half times), because every kept turn
        dragged another full render of team, map and actions along with it.

        It is also wrong on its own terms and not merely dear: a stale screen
        invites the model to reason about a map that has already changed, while
        the CURRENT one is right there in the fresh user message. What cannot be
        reconstructed from anywhere else is what it said and what the tools told
        it. That is what stays.

        In: the list of messages for the turn just finished. Out: nothing.
        """
        if self.cfg.scratch_turns <= 0:
            return
        kept = [
            {"role": "user",
             "content": "[the screen you were shown that turn, since changed]"}
            if m.get("role") == "user" else m
            for m in turn
        ]
        self._scratch.append(kept)
        self._scratch = self._scratch[-self.cfg.scratch_turns:]

    def _record_call(self, name: str, args: dict[str, Any]) -> None:
        """Keeps one tool call, as made, for this turn's trace.

        In: the tool name and its arguments. Out: nothing (appended to the log).
        """
        entry: dict[str, Any] = {"tool": name}
        for k in ("index", "id", "slot", "note", "route", "why"):
            v = args.get(k)
            if v not in (None, ""):
                entry[k] = v[:160] if isinstance(v, str) else v
        self._tool_calls.append(entry)

    def tool_calls_made(self) -> list[dict[str, Any]]:
        """The tool calls of the turn just decided, and clears them.

        In: nothing. Out: one dict per call, in the order the model made them.
        """
        # Read once per decision by whatever is logging, which is why it empties:
        # the next turn's calls must not carry the last turn's with them. `play` and
        # `set_lead` never reach `answer_tool`, so they are recorded in the loop
        # rather than here.
        calls, self._tool_calls = self._tool_calls, []
        return calls

    def tools(self) -> list[dict[str, Any]]:
        """Returns the tool declarations offered to the model.

        In: nothing. Out: list of OpenAI function-calling tool dicts.
        """
        cfg = getattr(self, "cfg", None) or self.config
        return build_tools(
            notes_cap=cfg.notes_cap,
            plan_chars=cfg.plan_chars,
            bag_tool=cfg.bag_tool,
            extra_tools=cfg.extra_tools,
        )

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call and returns the result shown to the model.

        In: tool name, arguments dict, and the current state. Out: the tool
        response string.
        """
        if name == "team_details":
            return render.team_view(state.get("team")) or "(empty team)"
        if name == "what_lies_ahead":
            return exits_text(state)
        if name in ("remember", "revise", "forget"):
            if self._notebook is None:
                return f"unknown tool: {name}"
            return self._notebook.handle(name, args)
        if name == "plan":
            if self.cfg.plan_chars <= 0:
                return f"unknown tool: {name}"
            return self._handle_plan(args)
        if name == "bag":
            if not self.cfg.bag_tool:
                return f"unknown tool: {name}"
            return self._handle_bag(state)
        return f"unknown tool: {name}"

    def render_state(self, state: dict[str, Any]) -> str:
        """Renders the state into text for the model. THE hook for changing that.

        In: the state dict. Out: a string the model reads as context for its
        decision.
        """
        return render_state_default(state, self.cfg.state_view, self.verbose)

    def _state_view_label(self) -> str:
        """Returns a short label for the view mode, for metadata recording."""
        overridden = type(self).render_state is not LLMBot.render_state
        return state_view_label(self.cfg.state_view, overridden)

    def _build_user_message(self, state: dict[str, Any]) -> str:
        """Assembles the full user message: view, journal, and instruction.

        In: the state dict. Out: the complete user-role message string.
        """
        notes_block = self._notebook.view_block() if self._notebook else None
        plan_block = self._plan_block() if self.cfg.plan_chars > 0 else None
        return build_user_message(
            state_view=self.render_state(state),
            journal=self.journal,
            n_actions=len(state["actions"]),
            notes_block=notes_block,
            plan_block=plan_block,
        )

    def _handle_plan(self, args: dict[str, Any]) -> str:
        """Handles the plan tool call: stores or replaces the route plan.

        In: the tool arguments. Out: confirmation shown to the model.
        """
        # Truncated rather than refused: a plan cut short is still a plan.
        route = str(args.get("route") or "").strip().replace("\n", " ")
        if not route:
            return "nothing to plan: `route` was empty."
        had = bool(self.plan)
        self.plan = route[: self.cfg.plan_chars]
        return (("plan replaced. " if had else "plan noted. ")
                + "You will see it every turn until you change it.")

    def _handle_bag(self, state: dict[str, Any]) -> str:
        """Handles the bag tool call: returns items the player is carrying.

        In: the state dict. Out: a comma-separated list of bag items.
        """
        bag = state.get("bag") or []
        return ", ".join(str(item) for item in bag) or "(empty)"

    def _plan_block(self) -> list[str]:
        """The current plan as lines for the user message, or an invitation.

        In: nothing. Out: lines to insert into the user message.
        """
        if not self.plan:
            return ["", "YOUR PLAN FOR THIS MAP: none yet. Use `plan` to write the "
                    "route you mean to take, before the first choice closes options "
                    "you wanted."]
        return ["", f"YOUR PLAN FOR THIS MAP (yours, change it with `plan`): "
                    f"{self.plan}"]

    def _exits_text(self, state: dict[str, Any]) -> str:
        """Describes where each legal action leads on the map."""
        return exits_text(state)

    def call_model(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Calls the model endpoint and updates token counters.

        In: the messages list (OpenAI format). Out: the assistant message dict.
        Raises LLMConfigError for permanent failures, LLMError for transient ones.
        """
        message, usage = call_model_http(
            messages=messages, model=self.model, endpoint=self.endpoint,
            token=self.token, tools=self.tools(),
            temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens,
            seed=self.seed, retries=self.cfg.retries,
            token_budget=self.cfg.token_budget, tokens_used=self.tokens_used,
        )
        self.calls += 1
        self.retry_count += usage.pop("retries", 0)
        self.tokens_in += usage.get("prompt_tokens", 0)
        self.tokens_out += usage.get("completion_tokens", 0)
        self.tokens_used += usage.get(
            "total_tokens",
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
        )
        return message

    @staticmethod
    def _as_index(v: Any) -> int | None:
        """Coerces a tool argument to an int index, tolerating string digits.

        In: any value (often a string like "2"). Out: the integer, or None.
        """
        return _as_index(v)

    @staticmethod
    def _parse_index(text: str, n: int) -> int | None:
        """Extracts the last valid action index from prose text.

        In: the model's prose and the number of legal actions. Out: the last
        integer in range [0, n), or None.
        """
        return _parse_index(text, n)
