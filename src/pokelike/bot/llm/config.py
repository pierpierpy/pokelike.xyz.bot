"""Configuration and error types for the LLM harness.

The LLMConfig class validates every knob an LLM bot can turn. The three error
classes separate what should stop the run (auth and budget errors) from what
should fall back (transient failures).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMError(RuntimeError):
    """Something went wrong on one call. The bot falls back and plays on."""


class LLMConfigError(LLMError):
    """The setup is wrong and every call will fail the same way.

    Raised on bad tokens, unknown models, or unreachable endpoints. This error
    stops the run immediately.
    """


class LLMBudgetError(LLMError):
    """The run asked for more tokens than the bot allowed itself.

    This error is only raised when a config sets `token_budget`.
    """


# --------------------------------------------------------------------- config

StateView = Literal["screen", "json", "both"] | list[str]


class LLMConfig(BaseModel):
    """This class holds every knob an LLM bot can turn, in one validated place.

        config = LLMConfig(prompt=GAME_RULES + "...", temperature=0.3)

    The model uses `extra="forbid"` so a typo in a field name is caught at
    construction time. Credentials are not stored here because this object is
    fingerprinted.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str = ""                            # the __init__.py module fills this after GAME_RULES exists
    model: str | None = None                    # pins a model id, or None to use $MODEL_ID
    temperature: float = 0.6
    max_tokens: int = 1500
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high"] | None = None
    # None omits the field entirely, for a model that rejects it. Everything else
    # is sent as OpenAI's reasoning_effort. Not every provider supports every
    # value; a model that only accepts a subset raises its own HTTP error.
    max_rounds: int = 4                          # maximum tool rounds before the turn is given up
    memory: int = 6                              # number of past turns replayed; -1 keeps all
    token_budget: int = 0                        # per-run token cap; 0 means no limit
    retries: int = 4                             # attempts on a transient HTTP failure
    extra_tools: list[dict[str, Any]] = Field(default_factory=list)
    state_view: StateView = "screen"             # determines what the model reads each turn

    # --- notebook (remember/revise/forget), opt-in by setting notes_cap > 0 ---
    notes_cap: int = 0                           # max notes; 0 disables the notebook
    note_chars: int = 160                        # character limit per note
    cross_run_memory: bool = False               # when True, notes survive reset()

    # --- plan tool, opt-in by setting plan_chars > 0 ---
    plan_chars: int = 0                          # max chars for the route plan; 0 disables the tool

    # --- bag tool, opt-in by setting bag_tool = True ---
    bag_tool: bool = False
    # Shared tools to leave out. Removing a tool that the view already answers
    # saves a round trip and the schema tokens every turn.
    drop_tools: tuple[str, ...] = ()

    # --- scratchpad, the last N finished turns travel verbatim ---
    scratch_turns: int = 0        # whole turns kept verbatim; 0 is off and -1 keeps all
    # This setting controls what fills the user slot of a kept turn:
    #   "line"  a single marker (cheapest)
    #   "brief" one line of facts about what changed
    #   "full"  the full screen as it was
    scratch_state: str = "line"
    # This tuple controls what survives when a campaign crosses from one region
    # into the next.
    keep_across_regions: tuple[str, ...] = ("notes",)

    @field_validator("drop_tools")
    @classmethod
    def _may_not_drop_play(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        # The play tool is how a turn ends; without it every turn would fall back.
        if "play" in v:
            raise ValueError("play cannot be dropped: it is how a turn ends")
        return v

    @field_validator("keep_across_regions")
    @classmethod
    def _known_memories(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        known = ("notes", "journal", "scratchpad", "plan")
        unknown = [x for x in v if x not in known]
        if unknown:
            raise ValueError(f"keep_across_regions: no memory called {unknown}. "
                             f"There is: {', '.join(known)}")
        return v

    @field_validator("scratch_state")
    @classmethod
    def _known_scratch_state(cls, v: str) -> str:
        if v not in ("line", "brief", "full"):
            raise ValueError('scratch_state must be "line", "brief" or "full"')
        return v

    @field_validator("scratch_turns")
    @classmethod
    def _scratch_turns_not_negative(cls, v: int) -> int:
        if v < -1:
            raise ValueError("scratch_turns must be -1 (keep all) or 0 or more")
        return v
