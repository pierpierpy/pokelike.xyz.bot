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
from .loop import run_turn
from .prompt import exits_text, render_state_default, state_view_label
from .record import build_artifacts, build_metadata
from .tools import CLOSING, GAME_RULES, TOOLS, _STOCK_TOOL_NAMES
from .transport import call_model_http

# Generation of the shared loop. Written into every result; a row measured under
# a different number is marked as such rather than ranked as if it were the same.
HARNESS = 1


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
        self._pending: tuple[int | None, int | None, str] | None = None

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

    def metadata(self) -> dict[str, Any]:
        """Returns run metadata for the registry and benchmark results.

        In: nothing. Out: a dict with model, harness, token counts, fallback_rate,
        and view/tool configuration.
        """
        return build_metadata(
            model=self.model, harness_version=self.harness_version,
            bot_class_name=type(self).__name__,
            calls=self.calls, turns=self.turns, tokens_used=self.tokens_used,
            tokens_in=self.tokens_in, tokens_out=self.tokens_out,
            retry_count=self.retry_count, fallbacks=self.fallbacks,
            temperature=self.cfg.temperature,
            tool_names=self.tool_names(), state_view_label=self._state_view_label(),
        )

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
        return run_turn(
            state=state, allow_lead=allow_lead,
            system_prompt=self.cfg.prompt,
            user_message=self._build_user_message(state),
            max_rounds=self.cfg.max_rounds,
            call_model_fn=self.call_model, answer_tool_fn=self.answer_tool,
            parse_index_fn=self._parse_index, as_index_fn=self._as_index,
        )

    def tools(self) -> list[dict[str, Any]]:
        """Returns the tool declarations offered to the model.

        In: nothing. Out: list of OpenAI function-calling tool dicts.
        """
        cfg = getattr(self, "cfg", None) or self.config
        return [*TOOLS, *cfg.extra_tools]

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call and returns the result shown to the model.

        In: tool name, arguments dict, and the current state. Out: the tool
        response string.
        """
        if name == "team_details":
            return render.team_view(state.get("team")) or "(empty team)"
        if name == "what_lies_ahead":
            return exits_text(state)
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
        return build_user_message(
            state_view=self.render_state(state),
            journal=self.journal,
            n_actions=len(state["actions"]),
        )

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
