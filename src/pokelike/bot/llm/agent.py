"""This module defines the LLMBot class and the one-call-per-turn decision loop.

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
from .decorator import collect_decorated_tools, dispatch_decorated_tool
from .tools import CLOSING, GAME_RULES, TOOLS, _STOCK_TOOL_NAMES, build_tools
from .transport import call_model_http

# This version of the shared loop is written into every result. A row measured
# under a different number is not ranked as if it were the same.
HARNESS = 2


class LLMBot(Bot):
    """A bot that asks a model what to do, one call per turn.

    Subclass this class and set `config` (at least a `prompt`) to get a bot that
    plays the game via an LLM endpoint, with tools, journal, and fallback.
    """

    name = "llm"
    harness_version = HARNESS
    config: LLMConfig = LLMConfig(prompt=GAME_RULES + CLOSING)

    def __init__(self, seed: int = 0, endpoint: str | None = None,
                 token: str | None = None, model: str | None = None,
                 config: LLMConfig | None = None, verbose: bool = False,
                 **overrides: Any) -> None:
        """Builds the bot and validates credentials and tool configuration.

        The endpoint, token, and model come from args or the environment.
        Raises LLMConfigError if credentials or tools are misconfigured.
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
        # The notebook is only constructed when notes_cap > 0.
        self._notebook: Notebook | None = None
        if self.cfg.notes_cap > 0:
            self._notebook = Notebook(self.cfg.notes_cap, self.cfg.note_chars)
        # The plan is a per-run route, only active when plan_chars > 0.
        self.plan: str = ""
        self._validate_tools()
        self._init_counters()

    def _validate_tools(self) -> None:
        """Verifies that the tool set includes `play` and has no duplicate names."""
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
        """Zeroes all mutable per-run state to initial values."""
        self.calls = self.turns = self.tokens_used = 0
        self.tokens_in = self.tokens_out = self.retry_count = self.fallbacks = 0
        self.journal: list[str] = []
        self._last_why = ""
        self._tool_calls: list[dict[str, Any]] = []
        self._opening: str = getattr(self, '_opening', '')
        self._pending: tuple[int | None, int | None, str] | None = None
        # The scratchpad holds the last N finished exchanges, carried verbatim.
        self._scratch: list[list[dict[str, Any]]] = []
        self._turn_state: dict[str, Any] | None = None
        # The last exchange with the model (for inspection after the turn).
        # Copied because the caller keeps appending to the same list.
        self.last_sent: list[dict[str, Any]] = []
        self.last_reply: dict[str, Any] | None = None

    def reset(self, seed: int) -> None:
        """Resets all per-run state for a new game with the given seed."""
        self.seed = seed
        self.journal = []
        self._pending = None
        self.calls = self.turns = self.tokens_used = self.fallbacks = 0
        self.tokens_in = self.tokens_out = self.retry_count = 0
        self._last_why = ""
        self._tool_calls: list[dict[str, Any]] = []
        self._opening: str = getattr(self, '_opening', '')
        # The plan and scratchpad are per-run because the plan describes a route
        # through this map, and the scratchpad is this episode's reasoning.
        self.plan = ""
        self._scratch: list[list[dict[str, Any]]] = []
        self._turn_state: dict[str, Any] | None = None
        # The notebook survives reset only when cross_run_memory is on.
        if self._notebook and not self.cfg.cross_run_memory:
            self._notebook.clear()

    def region_cleared(self, done: dict[str, Any]) -> str | None:
        """Returns the text the next region opens with when a campaign crosses one.

        The `done` dict contains region, next, badges, won, steps, and team.
        """
        # Memory is still intact here, so a subclass can call `call_model` with
        # `memory_text()` to produce a richer summary.
        kept = self.cfg.keep_across_regions
        carried = "your notes came with you" if "notes" in kept else "nothing came with you"
        team = ", ".join(done.get("team") or []) or "an empty team"
        return (f"YOU CLEARED {str(done.get('region', '')).upper()} with "
                f"{done.get('badges', 0)} badges, in {done.get('steps', 0)} steps, "
                f"finishing with {team}. Next: {str(done.get('next') or '').upper()}, "
                f"a new team from a new starter and eight different gyms. "
                f"The plan and your last turns did not come with you, "
                f"{carried}.")

    def region_opening(self, text: str) -> None:
        """Stores the text that the last region left for this one's first prompt."""
        # The text goes into the journal slot so the model sees it in the user
        # message, and the entry ages out naturally as the new region fills up.
        if text:
            self._opening = text.strip()

    def reset_memory(self, keep: tuple[str, ...] | None = None) -> None:
        """Forgets the region just finished, keeping only the specified parts.

        The `keep` tuple names which of notes, journal, scratchpad, and plan to
        retain. It defaults to the config policy when called with no argument.
        """
        keep = self.cfg.keep_across_regions if keep is None else keep
        if "journal" not in keep:
            self.journal = []
        if "scratchpad" not in keep:
            self._scratch = []
        if "plan" not in keep:
            self.plan = ""
        if "notes" not in keep and self._notebook is not None:
            self._notebook.notes.clear()

    def memory_text(self, include_scratch: bool = False) -> str:
        """Returns the memory as text, suitable for handing to a model."""
        parts = []
        if self._notebook is not None and self._notebook.notes:
            parts.append("NOTES\n" + "\n".join(
                f"  [{i}] {n}" for i, n in enumerate(self._notebook.notes, 1)))
        if self.plan:
            parts.append(f"PLAN\n  {self.plan}")
        if self.journal:
            parts.append("WHAT YOU DID\n" + "\n".join(self.journal))
        if include_scratch:
            # The scratchpad is flattened to strings here; the
            # `memory_messages()` method keeps the original message shape.
            for turn in self._scratch:
                for m in turn:
                    parts.append(f"{m.get('role')}: {(m.get('content') or '')[:400]}")
        return "\n\n".join(parts)

    def memory_messages(self, n: int | None = None) -> list[dict[str, Any]]:
        """Returns the kept turns as real messages, newest last.

        Only retained turns are returned because `scratch_turns` drops older
        turns as they age out. For a full region's history, use the journal.
        """
        turns = self._scratch if n is None else self._scratch[-n:]
        return [m for turn in turns for m in turn]

    def metadata(self) -> dict[str, Any]:
        """Returns run metadata for the registry and benchmark results.

        The dict includes model, harness version, token counts, fallback_rate,
        and view/tool configuration.
        """
        meta = build_metadata(
            model=self.model, harness_version=self.harness_version,
            bot_class_name=type(self).__name__,
            calls=self.calls, turns=self.turns, tokens_used=self.tokens_used,
            tokens_in=self.tokens_in, tokens_out=self.tokens_out,
            retry_count=self.retry_count, fallbacks=self.fallbacks,
            temperature=self.cfg.temperature,
            reasoning_effort=self.cfg.reasoning_effort,
            tool_names=self.tool_names(), state_view_label=self._state_view_label(),
        )
        # The result also records notebook/plan settings and current state, so
        # readers know what the bot was allowed to do and what it held at the end.
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
        if self.cfg.scratch_turns != 0:
            meta["scratch_turns"] = self.cfg.scratch_turns
            meta["scratch_state"] = self.cfg.scratch_state
            meta["scratch_held"] = len(self._scratch)
        # Decorated tools are recorded so the result shows which extra tools were
        # available.
        dec = collect_decorated_tools(type(self))
        if dec:
            meta["decorated_tools"] = [t["function"]["name"] for t in dec]
        return {**meta, **self.add_metadata()}

    def tool_names(self) -> list[str]:
        """Returns the names of all tools offered to the model on each turn."""
        return [t["function"]["name"] for t in self.tools()]

    def artifacts(self) -> list:
        """Returns the Artifact objects a submission of this bot carries for the record."""
        return build_artifacts(
            bot_class_name=type(self).__name__, prompt=self.cfg.prompt,
            model=self.model, model_pinned=type(self).config.model is not None,
            harness_version=self.harness_version,
            temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens,
            reasoning_effort=self.cfg.reasoning_effort,
            max_rounds=self.cfg.max_rounds, memory=self.cfg.memory,
            token_budget=self.cfg.token_budget,
            tool_names=self.tool_names(), state_view_label=self._state_view_label(),
        )

    def reason(self) -> str:
        """Returns the model's explanation string for the last decision made."""
        return self._last_why

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Decides who leads, in the same model call as the move.

        Returns a (from, to) swap pair, or None if no reorder is needed.
        """
        # One HTTP call per turn. The reorder method runs first and caches the
        # move for act. This is offered only on the map screen because elsewhere
        # the options are the team itself.
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

        Returns the index of the chosen action within `state["actions"]`.
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
        """Records a decision into the journal and returns the chosen index."""
        self._last_why = why
        self.journal.append(journal_entry(state, index, why))
        self.journal = trim_journal(self.journal, self.cfg.memory)
        if self.verbose:
            print(f"   [llm] -> [{index}] {why[:100]}")
        return index

    def _run_fallback(self, state: dict[str, Any], reason: str) -> int:
        """Counts a fallback event and returns the backup heuristic's choice."""
        self.fallbacks += 1
        self._last_why = f"(fell back: {reason})"
        if self.verbose:
            print(f"   [llm] fallback: {reason}")
        return self.fallback_move(state)

    def fallback_move(self, state: dict[str, Any]) -> int:
        """Returns a safe action when the model does not answer correctly.

        The heuristic prefers healing when someone is hurt, then widening the
        team.
        """
        return fallback_move_default(state)

    def _run_turn(self, state: dict[str, Any],
                  allow_lead: bool = False) -> tuple[int, str, int | None]:
        """Runs one turn of the agentic loop until play() is called.

        Returns a tuple of (action index, reason string, lead slot or None).
        """
        # The scratchpad is flattened into the history that the loop inserts
        # between the system prompt and the fresh user message. When
        # scratch_turns is 0, the list is empty and the messages are exactly
        # [system, user].
        self._turn_state = state
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
            # The rounds are exhausted, but the exchange is kept so the next turn sees it.
            self._remember_turn(exc.this_turn)
            raise LLMError(str(exc)) from exc
        self._remember_turn(this_turn)
        return index, why, lead

    def render_scratch(self, state: dict[str, Any]) -> str:
        """Returns the text a kept turn shows where its original screen used to be."""
        # Override render_scratch to control how much of a kept turn the model
        # sees.
        mode = self.cfg.scratch_state
        if mode == "full":
            return self.render_state(state)
        if mode == "brief":
            return self._brief_state(state)
        return "[the screen you were shown that turn, since changed]"

    def _brief_state(self, state: dict[str, Any]) -> str:
        """Returns one line of facts about a turn, for `scratch_state="brief"`."""
        # This includes position, progress, and team health because those
        # change per turn. The map and options are omitted because they go stale
        # immediately.
        run = state.get("run") or {}
        team = ", ".join(
            f"{p.get('name')} L{p.get('level')} {p.get('hp')}/{p.get('max_hp')}"
            for p in (state.get("team") or [])[:6])
        return (f"[that turn: step {state.get('steps')}, {state.get('screen')}, "
                f"map {run.get('map', state.get('map', 0))}, "
                f"badges {run.get('badges', 0)}"
                + (f", team {team}" if team else "") + "]")

    def _remember_turn(self, turn: list[dict[str, Any]]) -> None:
        """Adds one finished exchange to the scratchpad, dropping the oldest first.

        The user message in the kept turn is replaced by a brief summary from
        render_scratch, because the full screen is stale and expensive. Only the
        model's reasoning and tool responses are kept verbatim.
        """
        if self.cfg.scratch_turns == 0:
            return
        shown = self.render_scratch(self._turn_state or {})
        kept = [
            {"role": "user", "content": shown} if m.get("role") == "user" else m
            for m in turn
        ]
        self._scratch.append(kept)
        if self.cfg.scratch_turns > 0:
            self._scratch = self._scratch[-self.cfg.scratch_turns:]

    def _record_call(self, name: str, args: dict[str, Any]) -> None:
        """Appends one tool call to this turn's trace for later inspection."""
        entry: dict[str, Any] = {"tool": name}
        for k in ("index", "id", "slot", "note", "route", "why"):
            v = args.get(k)
            if v not in (None, ""):
                entry[k] = v[:160] if isinstance(v, str) else v
        self._tool_calls.append(entry)

    def tool_calls_made(self) -> list[dict[str, Any]]:
        """Returns the tool calls of the turn just decided, then clears the list.

        Each entry is one dict per call, in the order the model made them.
        """
        # The list is emptied after reading so the next turn starts clean.
        # The `play` and `set_lead` calls are recorded by the loop itself.
        calls, self._tool_calls = self._tool_calls, []
        return calls

    def tools(self) -> list[dict[str, Any]]:
        """Returns the tool declarations offered to the model.

        The result is a list of OpenAI function-calling tool dicts.
        When names collide, precedence is @tool methods over extra_tools over shared.
        """
        cfg = getattr(self, "cfg", None) or self.config
        return build_tools(
            notes_cap=cfg.notes_cap,
            plan_chars=cfg.plan_chars,
            bag_tool=cfg.bag_tool,
            drop_tools=cfg.drop_tools,
            extra_tools=cfg.extra_tools,
            decorated_tools=collect_decorated_tools(type(self)),
        )

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call and returns the result shown to the model.

        Decorated @tool methods are tried first, then the shared implementations.
        """
        # Decorated tools get first shot because they are the most specific.
        result = dispatch_decorated_tool(self, name, args, state)
        if result is not None:
            return result
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
        """Renders the state into text for the model.

        Override this method to change what the model sees each turn.
        """
        return render_state_default(state, self.cfg.state_view, self.verbose)

    def _state_view_label(self) -> str:
        """Returns a short label describing the view mode, for metadata recording."""
        overridden = type(self).render_state is not LLMBot.render_state
        return state_view_label(self.cfg.state_view, overridden)

    def _build_user_message(self, state: dict[str, Any]) -> str:
        """Assembles the full user message from the view, journal, and instruction."""
        notes_block = self._notebook.view_block() if self._notebook else None
        plan_block = self._plan_block() if self.cfg.plan_chars > 0 else None
        # Show the region-crossing note only until the journal has real entries.
        journal = self.journal
        if self._opening and not journal:
            journal = [f"LAST REGION: {self._opening}"]
        return build_user_message(
            state_view=self.render_state(state),
            journal=journal,
            n_actions=len(state["actions"]),
            notes_block=notes_block,
            plan_block=plan_block,
        )

    def _handle_plan(self, args: dict[str, Any]) -> str:
        """Handles the plan tool call by storing or replacing the route plan."""
        # The plan is truncated if too long because a cut-short plan is still
        # useful.
        route = str(args.get("route") or "").strip().replace("\n", " ")
        if not route:
            return "nothing to plan: `route` was empty."
        had = bool(self.plan)
        self.plan = route[: self.cfg.plan_chars]
        return (("plan replaced. " if had else "plan noted. ")
                + "You will see it every turn until you change it.")

    def _handle_bag(self, state: dict[str, Any]) -> str:
        """Returns a comma-separated list of items the player is carrying."""
        bag = state.get("bag") or []
        return ", ".join(str(item) for item in bag) or "(empty)"

    def _plan_block(self) -> list[str]:
        """Returns the current plan as lines for the user message, or an invitation."""
        if not self.plan:
            return ["", "YOUR PLAN FOR THIS MAP: none yet. Use `plan` to write the "
                    "route you mean to take, before the first choice closes options "
                    "you wanted."]
        return ["", f"YOUR PLAN FOR THIS MAP (yours, change it with `plan`): "
                    f"{self.plan}"]

    def _exits_text(self, state: dict[str, Any]) -> str:
        """Returns a description of where each legal action leads on the map."""
        return exits_text(state)

    def call_model(self, messages: list[dict[str, Any]],
                   tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Calls the model endpoint and updates token counters.

        Returns the assistant message dict. Raises LLMConfigError for permanent
        failures and LLMError for transient ones.
        """
        message, usage = call_model_http(
            messages=messages, model=self.model, endpoint=self.endpoint,
            # Passing `tools=[]` asks the model for prose only, while None
            # means the bot's usual tool set.
            token=self.token, tools=self.tools() if tools is None else tools,
            temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens,
            reasoning_effort=self.cfg.reasoning_effort,
            seed=self.seed, retries=self.cfg.retries,
            token_budget=self.cfg.token_budget, tokens_used=self.tokens_used,
        )
        # Copied because the caller keeps appending to the same list.
        self.last_sent = [dict(m) for m in messages]
        self.last_reply = message
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
        """Coerces a tool argument to an int index, tolerating string digits."""
        return _as_index(v)

    @staticmethod
    def _parse_index(text: str, n: int) -> int | None:
        """Extracts the last valid action index from prose text.

        Returns the last integer in range [0, n) found in the text, or None.
        """
        return _parse_index(text, n)
