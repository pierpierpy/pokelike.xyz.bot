"""Frozen harness for the model benchmark, v0.

This file is a self-contained copy of the LLM bot harness. Every model measured
under v0 ran against exactly this code. Do not edit once results exist beside it;
an improvement belongs in a new version directory.

The renderer (render.py beside this file) is not frozen here. Each result records
a sha256 of both this file and the renderer it ran against, so drift between them
is detected.
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

# The renderer beside this file is loaded by path because relative imports have
# no parent package here, and all harness directories share the name `harness`,
# which means a plain import would collide in sys.modules.
_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    f"pokelike_harness_{_HERE.parent.name}_render", _HERE / "render.py"
)
render = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = render
_spec.loader.exec_module(render)

# Decision method identifier. This value is written into every result; rows
# measured under a different number are marked as incomparable.
#
#   1  agentic loop with team_details / what_lies_ahead / set_lead / play,
#      situation rendered by core.render.screen, prose index as a last resort
HARNESS = 1


# ---------------------------------------------------------------- game rules
#
# Shared facts about the game, given to every model identically.

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
# These tools are shared by default so the comparison is fair. A bot may add its
# own or replace them (see `tools()` and `answer_tool()` on HarnessV0), and that
# fact is recorded in the result.

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
    """Something went wrong on one call, so the harness falls back and plays on."""


class LLMConfigError(LLMError):
    """The setup is wrong and every call will fail the same way.

    Covers situations such as:

    - bad token
    - unknown model name
    - non-OpenAI-compatible URL

    Falling back on these would play the whole run on the backup heuristic
    and file the result as an LLM entry, so these stop the run instead.
    """


class LLMBudgetError(LLMError):
    """The run asked for more tokens than the bot allowed itself.

    The harness only raises this error when a bot sets `TOKEN_BUDGET`.
    """


# ------------------------------------------------------------------------ bot


class HarnessV0(Bot):
    """A bot that asks a model what to do, one call per turn.

    Subclass this and set `PROMPT`. Everything else has a working default.

    | attribute      | what it decides                                |
    |----------------|------------------------------------------------|
    | `PROMPT`       | the system prompt (the submission itself)      |
    | `MODEL`        | model id, or None to take `$MODEL_ID`          |
    | `TEMPERATURE`  | sampling temperature                           |
    | `MAX_TOKENS`   | ceiling on one answer                          |
    | `MAX_ROUNDS`   | tool rounds before the turn is given up on     |
    | `MEMORY`       | how many past turns are shown back to the model|
    | `TOKEN_BUDGET` | tokens per run, 0 for no ceiling               |
    | `EXTRA_TOOLS`  | additional tools on top of the shared four      |
    | `STATE_VIEW`   | what the model reads each turn                 |

    `STATE_VIEW` options:

    | value | what the model gets | roughly |
    |---|---|--:|
    | `"screen"` | the ASCII view a person sees (default) | 880 chars |
    | `"json"` | the whole state dict, compact JSON | 5900 chars |
    | `"both"` | the view, then the dict under it | 6800 chars |
    | `["team", "actions"]` | just those keys, as JSON | varies |

    Override `render_state(state)` when none of the four fit. The harness adds
    the journal and instruction line around whatever `render_state` returns.

    To add tools, declare them in `EXTRA_TOOLS` and answer them in
    `answer_tool`. To replace the shared set entirely, override `tools()`.
    Both are recorded in the result.

    Pin `MODEL` in the bot file for a fixed standings row. Leave it None to
    play whatever `$MODEL_ID` names.
    """

    name = "llm-bench-v0"

    HARNESS = HARNESS
    PROMPT = GAME_RULES + CLOSING
    MODEL: str | None = None
    TEMPERATURE = 0.0
    MAX_TOKENS = 1500
    MAX_ROUNDS = 4
    MEMORY = 6
    TOKEN_BUDGET = 0
    # The number of additional retry attempts for rate limits and 5xx errors.
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
        # without editing the bot file.
        self.system = overrides.pop("prompt", None) or self.PROMPT
        self.temperature = overrides.pop("temperature", self.TEMPERATURE)
        self.max_tokens = overrides.pop("max_tokens", self.MAX_TOKENS)
        self.max_rounds = overrides.pop("max_rounds", self.MAX_ROUNDS)
        self.memory = overrides.pop("memory", self.MEMORY)
        # Also settable at instantiation for experiments without separate bot
        # folders. A submission should declare the value on the class so the
        # fingerprint captures the setting.
        self.state_view = overrides.pop("view", None) or self.STATE_VIEW
        self.token_budget = overrides.pop("token_budget", self.TOKEN_BUDGET)
        if overrides:
            raise TypeError(f"unknown settings: {', '.join(sorted(overrides))}")
        self.verbose = verbose or bool(os.environ.get("POKELIKE_VERBOSE"))

        # Checked once here because without `play` the model cannot end a turn,
        # so every turn would exhaust its rounds and fall back silently.
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
        # Tool calls since the last decision was logged, drained by
        # `tool_calls_made`. Includes calls from `reorder` (which runs before
        # `act`).
        self.tool_log: list[dict[str, Any]] = []
        self._last_why = ""
        # The turn decided in `reorder`, waiting for `act` to collect it.
        self._pending: tuple[int | None, int | None, str] | None = None

    # ------------------------------------------------------------------ hooks

    def reset(self, seed: int) -> None:
        self.seed = seed
        self.journal = []
        self._pending = None
        self.calls = self.turns = self.tokens_used = self.fallbacks = 0
        self.tokens_in = self.tokens_out = self.retries = 0
        self._last_why = ""

    def metadata(self) -> dict[str, Any]:
        """Returns data written into the run registry and the benchmark result."""
        return {
            "model": self.model,
            "harness": self.HARNESS,
            "bot": type(self).__name__,
            "calls": self.calls,
            "turns": self.turns,
            "tokens": self.tokens_used,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            # These are transient failures retried rather than counted against the model.
            "retries": self.retries,
            "fallbacks": self.fallbacks,
            "fallback_rate": round(self.fallbacks / self.turns, 3) if self.turns else 0.0,
            "temperature": self.temperature,
            # False means this bot had non-standard tools, so the row answers
            # a different question.
            "stock_tools": self.tool_names() == _STOCK_TOOL_NAMES,
            # Records what the model saw each turn. Different views are not comparable.
            "state_view": self.view_name(),
            "reproducible": False,
        }

    def _note_call(self, name: str, args: dict[str, Any]) -> None:
        """Record one tool call as it is made, before it is executed."""
        entry: dict[str, Any] = {"tool": name}
        for k in ("index", "id", "slot", "note", "route", "why"):
            v = args.get(k)
            if v not in (None, ""):
                entry[k] = v if not isinstance(v, str) else v[:160]
        self.tool_log.append(entry)

    def tool_calls_made(self) -> list[dict[str, Any]]:
        """Return and clear all calls since last asked, draining per decision."""
        out, self.tool_log = self.tool_log, []
        return out

    def tool_names(self) -> list[str]:
        return [t["function"]["name"] for t in self.tools()]

    def artifacts(self) -> list:
        """Returns the prompt and model reference recorded with a submission."""
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
        """Decide team lead in the same model call as the move.

        The run loop calls this before `act`. The agentic loop runs here and
        caches the result, so `act` returns the cached answer without a second
        request. The lead swap is only offered on the map screen, because
        elsewhere the options are the team itself and reordering would change
        what an index means.
        """
        self._pending = None
        if state.get("screen") != "map-screen" or not state.get("can_reorder"):
            return None
        try:
            index, why, lead = self._agentic_round(state, allow_lead=True)
        except LLMConfigError:
            raise
        except Exception:  # noqa: BLE001 - handled again, and counted, in act
            return None
        team = state.get("team") or []
        if lead is None or not 0 < lead < len(team):
            self._pending = (state.get("steps"), index, why)
            return None
        # Include lead decision in the explanation for the trace.
        why = f"lead {team[lead]['name']} | {why}"
        self._pending = (state.get("steps"), index, why)
        return (0, lead)

    def act(self, state: dict[str, Any]) -> int:
        self.turns += 1
        n = len(state["actions"])
        # The action was already decided in reorder(), guarded by `steps` to
        # prevent replaying against a different turn.
        if self._pending and self._pending[0] == state.get("steps"):
            _, index, why = self._pending
            self._pending = None
            if isinstance(index, int) and 0 <= index < n:
                return self._commit(state, index, why)
        try:
            index, why, _ = self._agentic_round(state)
        except (LLMConfigError, LLMBudgetError):
            # These errors are not recoverable because reruns fail identically or
            # the budget is spent.
            raise
        except Exception as e:  # noqa: BLE001 - transient failure must not end the run
            return self._run_fallback(state, f"{type(e).__name__}: {e}"[:80])

        if not isinstance(index, int) or not 0 <= index < n:
            return self._run_fallback(state, f"model returned index {index}")
        return self._commit(state, index, why)

    def _commit(self, state: dict[str, Any], index: int, why: str) -> int:
        self._last_why = why
        self.journal.append(f"step {state.get('steps')}: [{index}] {why[:90]}")
        self.journal = self.journal[-self.memory:]
        if self.verbose:
            print(f"   [llm] -> [{index}] {why[:100]}")
        return index

    def _run_fallback(self, state: dict[str, Any], reason: str) -> int:
        self.fallbacks += 1
        self._last_why = f"(fell back: {reason})"
        if self.verbose:
            print(f"   [llm] fallback: {reason}")
        return self.fallback_move(state)

    def fallback_move(self, state: dict[str, Any]) -> int:
        """Backup choice when the model fails to answer or returns out-of-range.

        The heuristic prefers healing when hurt, and otherwise widens the team.
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
            msg = self.call_model(messages)
            calls = msg.get("tool_calls") or []
            if not calls:
                # The model called no tool, so try to extract an index from prose.
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
                self._note_call(name, args)

                if name == "play":
                    return args.get("index"), str(args.get("why", "")), lead

                if name == "set_lead":
                    # The request is recorded but not applied here; the run loop performs the swap.
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

        raise LLMError(f"no call to play() within {self.max_rounds} rounds")

    # ------------------------------------------------------------------ tools

    def tools(self) -> list[dict[str, Any]]:
        """The tools offered to the model, in OpenAI function-calling form.

        Returns the shared four plus `EXTRA_TOOLS`. Override to replace them,
        but `play` must survive or every turn falls back.
        """
        return [*TOOLS, *self.EXTRA_TOOLS]

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answer one tool call. Override for custom tools and call `super()` for
        the shared ones. An unknown name returns a message rather than raising.
        """
        if name == "team_details":
            return render.team_view(state.get("team")) or "(empty team)"
        if name == "what_lies_ahead":
            return self._exits(state)
        return f"unknown tool: {name}"

    # ---------------------------------------------------------------- context

    def render_state(self, state: dict[str, Any]) -> str:
        """What the model reads each turn. Override for custom views.

        The method reads `STATE_VIEW`. The harness wraps the result with the
        journal and instruction line, so replacing this method cannot break those.
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
        """Returns the setting name, or 'custom' if `render_state` was overridden."""
        if type(self).render_state is not HarnessV0.render_state:
            return "custom"
        return self.state_view if isinstance(self.state_view, str) else \
            "keys:" + ",".join(self.state_view)

    def _situation(self, state: dict[str, Any]) -> str:
        """Build the full user message from the view, journal, and instruction line."""
        parts = [self.render_state(state)]
        if self.journal:
            parts += ["", "YOUR RECENT MOVES:", *(f"  {r}" for r in self.journal)]
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
            # Passed for best-effort reproducibility, but most providers ignore it.
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
        # Retried with backoff for transient failures (rate limits, 5xx).
        # Auth and model-not-found are not retried because they fail identically.
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
        """Attempts to fish a valid index out of a prose answer as a last resort."""
        import re

        for m in re.finditer(r"\[?(\d+)\]?", text):
            v = int(m.group(1))
            if 0 <= v < n:
                return v
        return None
