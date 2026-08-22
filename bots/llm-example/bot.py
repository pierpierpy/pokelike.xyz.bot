"""llm-example: every knob of harness generation 1, and what each one costs.

    uv run pokelike bot run --bot llm-example --runs 1 -d

Credentials come from `.env` at the repository root, so nothing goes on the command line.

A reference, not a contender. It changes everything at once, which shows the surface
and ruins the score. Not benchmarked. Copy the parts you want.

For generation 2 (a notebook, a plan, and kept turns) see
[llm-example2](../llm-example2/). This file is the generation-1 surface: the same four
tools, one user message, no memory beyond the journal.

ONE TURN IS ONE HTTP POST, and this is the whole body:

    {"model": ..., "temperature": ..., "max_tokens": ..., "seed": ...,
     "tool_choice": "auto",
     "tools": [...],                 <- tools(), and THIS IS PROMPT      1137 char
     "messages": [
       {"role": "system"},           <- config.prompt                    1665 char
       {"role": "user"},             <- render_state + journal + range     940 char
       {"role": "assistant"},        <- what the model just said
       {"role": "tool"},             <- answer_tool returned it, ALSO PROMPT
     ]}

So the floor, before the model has asked for anything:

    llm-survivor    1665 system + 1137 tools +  831 view  =  3633 char/turn
    llm-example     1833 system + 1676 tools +  390 view  =  3899 char/turn

The four shared tool schemas are 1137 characters, MORE than the 831 of the state view
itself. A fifth tool is not free because the model never calls it: you pay for its
schema every turn of every run. And a tool that answers with three kilobytes has cost
more than sending the whole state would have.

Budget: about 30k tokens a run, so ~1.5M for a fifty-seed entry. `state_view="json"`
is about 6x that.
"""

from __future__ import annotations

import json
from typing import Any

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig, tool
from pokelike.core import render


class ExampleBot(LLMBot):
    name = "llm-example"

    # ---------------------------------------------------------------- 1. the prompt
    # The whole submission, for most LLM bots. GAME_RULES is the factual half, read
    # out of the game bundle rather than guessed. Sent unchanged every turn.

    PROMPT = GAME_RULES + """
PLAY LIKE THIS
- Read the numbers you are given rather than working them out. HP is already a
  percentage and the exits are already listed; arithmetic is where you slip.
- Ask `bag` before spending a turn on an item node. A second potion is worth less
  than almost anything else that turn could buy.
- Weigh `set_lead` on every map turn. It is free, and who enters the battle first
  decides most battles.
- Call `state_json` when something you need is genuinely not above. It costs about
  six times the rest of the message, so do not call it out of habit.

Think briefly, then call `play`. Always call `play`."""

    # ------------------------------------------------- 2. its own tools
    # @tool is the whole declaration: name from the method, parameters from the
    # signature. The description is prompt, re-sent every turn, so say when NOT to
    # call it too.

    @tool("The raw state dict as JSON: team, bag, map, run, actions, stats, "
          "type_items. Everything the Python bots see. Use it when what you need is "
          "not in the summary.",
          part="one key, or 'all'. One key is far cheaper: the whole dict is about "
               "5900 characters.")
    def state_json(self, state: dict[str, Any], part: str = "all") -> str:
        """In: the state and which key to send. Out: that part as compact JSON."""
        if part != "all" and part not in state:
            return f"no key '{part}'. There is: {', '.join(sorted(state))}"
        payload = state if part == "all" else {part: state[part]}
        text = json.dumps(payload, separators=(",", ":"))
        # Truncated on purpose: a late-run map is large, and a reply that fills the
        # context costs the model the reasoning it was about to do.
        return text if len(text) <= 4000 else text[:4000] + " ...(truncated)"

    @tool("What you are carrying, by name.")
    def bag(self, state: dict[str, Any]) -> str:
        """In: the state. Out: the bag, or a note that it is empty."""
        return ", ".join(state.get("bag") or []) or "(carrying nothing)"

    # ------------------------------------------------------------------ 3. the knobs
    config = LLMConfig(
        prompt=PROMPT,
        temperature=0.3,        # low, not zero: zero is not reproducible either
        max_tokens=900,         # a short reason plus a tool call
        max_rounds=6,           # this prompt asks for two tools before play
        memory=8,               # journal lines: enough to notice it is going in circles
        token_budget=60_000,    # ~2x a normal run. Hitting it ENDS the run
        state_view="screen",    # IGNORED HERE: section 4 replaces render_state, which is
                                # the only thing that reads it. "json" is ~6x the tokens
    )

    # A tool that raises is answered, not lost: the loop would otherwise treat the
    # exception as a turn the model failed to take, and play the fallback instead.

    # ------------------------------------------------------------------- 4. the view
    def render_state(self, state: dict[str, Any]) -> str:
        """In: the state. Out: the state as prose, with the arithmetic done."""
        # Three changes from the built-in view: HP as a percentage (the model should
        # not have to divide), the consequence written instead of drawn, and the exits
        # inline (asking for them costs a round trip).
        #
        # `_build_user_message` is NOT the seam. The journal and the "pick an index
        # between 0 and N" line are added around whatever this returns, so replacing
        # the view cannot cost the bot its memory or leave the model without the range.
        run = state.get("run") or {}
        team = state.get("team") or []
        # Named when it is not Kanto, as the built-in view does it: a custom view
        # that drops the region is a model playing Johto believing it is in Kanto.
        where = state.get("region") or "kanto"
        parts = [f"TURN {state.get('steps', 0)}, map {run.get('map', 0)}, "
                 f"{run.get('badges', 0)} badges, {len(team)} Pokemon alive."
                 + (f" Region: {where}." if where != "kanto" else "")]

        if team:
            parts += ["", "YOUR TEAM"]
            for i, p in enumerate(team):
                pct = f"{p['hp'] / p['max_hp']:.0%}" if p.get("max_hp") else "?"
                move = p.get("move") or {}
                lead = "   <- LEADS THE NEXT BATTLE" if i == 0 else ""
                parts.append(
                    f"  {i}. {p['name']:<12} Lv{p.get('level', '?'):<3} {pct:>4} HP  "
                    f"{'/'.join(p.get('types') or []) or '?':<14}"
                    f"{move.get('name', '-')} {move.get('power', '')}{lead}")

        bag = state.get("bag") or []
        parts += ["", f"CARRYING: {', '.join(bag) if bag else 'nothing'}", "", "YOUR OPTIONS"]
        exits = render.exits_of(state, unique=True)
        for i, a in enumerate(state.get("actions") or []):
            after = f"  -> then you could reach: {', '.join(exits[i])}" if exits.get(i) else ""
            parts.append(f"  [{i}] {a.get('node') or a.get('label', '')}{after}")
        if state.get("screen") == "map-screen" and len(state.get("actions") or []) > 1:
            parts.append("  Taking one of these closes the others for good.")
        return "\n".join(parts)

    # ------------------------------------------------------- 5. when it does not answer
    def fallback_move(self, state: dict[str, Any]) -> int:
        """In: the state. Out: the index to play when the model did not answer."""
        # Overriding this is rarely wise: it plays under your bot's name on every turn
        # the model missed, and `fallback_rate` reports the share. A clever fallback is
        # cleverness measured as though the model produced it.
        actions = state["actions"]
        team = state.get("team") or []
        hurt = any(p["hp"] / p["max_hp"] < 0.4 for p in team if p.get("max_hp"))
        for want in (("pokecenter",) if hurt else ()) + ("catch", "pokecenter"):
            for i, a in enumerate(actions):
                if a.get("node") == want:
                    return i
        return 0

    # ---------------------------------------------------------------- 6. what is filed
    def add_metadata(self) -> dict[str, Any]:
        """In: nothing. Out: my own facts, merged into what is recorded."""
        # Only what nothing else could know. Never the token or the endpoint: a result
        # file is the kind of thing that gets pasted into an issue.
        return {"extra_tools": [t["function"]["name"] for t in self.cfg.extra_tools]}

    # `call_model(messages) -> message dict` is the one hook this file does not use.
    # Override it for a model that is not an OpenAI-compatible HTTP endpoint: return
    # `content` plus `tool_calls` as [{"id", "function": {"name", "arguments"}}] with
    # `arguments` a JSON string, keep the counters, and raise LLMConfigError for what
    # will fail forever, LLMError for what is transient.
