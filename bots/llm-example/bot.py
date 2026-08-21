"""llm-example: every parameter you can play with, and where each one lands.

    export FW_ENDPOINT="https://..."   # base URL, no /v1
    export FW_TOKEN="..."
    export MODEL_ID="..."
    uv run pokelike bot run --bot llm-example --runs 1 -d

**A reference, not a contender.** The other `llm-*` bots each move one thing, so
comparing them means something; this one moves everything at once, which is the
right way to show the surface and the wrong way to learn from a score. It is not
benchmarked. Copy the parts you want.


================================================================================
WHAT ACTUALLY GETS SENT, EVERY TURN
================================================================================

One turn is one HTTP POST to `{FW_ENDPOINT}/v1/chat/completions`, and this is
the whole body. Every line is tuned somewhere, and the right-hand column says
where:

    {
      "model":       "glm-5.2",       <- config.model, or $MODEL_ID if None
      "temperature": 0.6,             <- config.temperature
      "max_tokens":  1500,            <- config.max_tokens
      "seed":        42,              <- the run seed. Best effort; most
                                         providers ignore it
      "tool_choice": "auto",          <- fixed by the harness
      "tools":       [ ... ],         <- tools() = shared four + config.extra_tools.
                                         THIS IS PROMPT TOO             1137 ch
      "messages": [
        {"role": "system",    ...},   <- config.prompt                 1665 ch
        {"role": "user",      ...},   <- _build_user_message(state)     940 ch
        {"role": "assistant", ...},   <- what the model just said
        {"role": "tool",      ...},   <- answer_tool() returned this,
                                         ALSO PROMPT                    135 ch
        ...                              up to config.max_rounds times
      ]
    }

**A tool is two prompt surfaces, not one**, and this is the thing people miss:

  * its **definition** — the `description` fields you write in `config.extra_tools` —
    is documentation the model reads, and it is re-sent on **every turn**;
  * its **result** — whatever `answer_tool` returns — is text the model reads too.

Measured on `llm-survivor`, the four shared tool schemas are **1137 characters,
more than the 831 of the state view itself**, and 423 of those are pure
`description` prose. A fifth tool is not free just because the model never calls
it: you pay for its schema every turn of every run. And a tool that returns
three kilobytes has cost more than the state it was meant to save you from
sending.

So the floor, before the model has asked for anything at all:

    llm-survivor    1665 system + 1137 tools +  831 view  =  3633 char/turn
    llm-example     1833 system + 1676 tools +  390 view  =  3899 char/turn

The `user` message, the only part that changes turn to turn, is built from
three pieces — one yours, two the harness's:

    _build_user_message(state)
    ├── render_state(state)               <- YOURS. config.state_view, or override it
    ├── "YOUR RECENT MOVES:" + journal    <- harness. Length is config.memory
    └── "Pick an index between 0 and N"   <- harness. Never yours to drop

That split is deliberate. The old design had all three in one method, so a bot
that replaced it to change the view silently lost its memory and stopped telling
the model how many options there were — and kept running, just worse, with
nothing reporting it. Now `render_state()` can return anything at all and the
other two are still there.


================================================================================
EVERY KNOB, IN ONE PLACE
================================================================================

All knobs are fields of `config = LLMConfig(...)`, a pydantic model set on the class:

    field               default     what it decides
    ────────────────────────────────────────────────────────────────────────
    prompt              GAME_RULES  the system message. For most bots, the
                                    whole submission
    state_view          "screen"    WHAT THE MODEL SEES each turn:
                                      "screen"  the rendered view    ~880 ch
                                      "json"    the whole state dict ~5900 ch
                                      "both"    the view, then the dict
                                      ["team", "actions", ...]  those keys only
    render_state(state) -           the same thing, when none of those four fit
    extra_tools         []          tools of your own, on top of the shared four
    answer_tool(n,a,s)  -           what they answer
    tools()             shared+extra the whole set, if you would rather rebuild it
    model               None        pin a model id, or take $MODEL_ID
    temperature         0.6         sampling
    max_tokens          1500        ceiling on one answer
    max_rounds          4           tool rounds before the turn is given up on
    memory              6           past turns replayed to the model
    token_budget        0           per-run ceiling; 0 = none. ~30k is one run
    fallback_move(state) heal/catch what to play when the model does not answer
    call_model(messages) HTTP       THE MODEL ITSELF. Override for a local one
    reason()            the reason  one line per decision in `-d` logs
    metadata()          see below   what is recorded beside your score

Credentials are never any of these. `FW_ENDPOINT` and `FW_TOKEN` come from the
environment, always. The model ID is not a secret and pinning it is encouraged:
it goes into the fingerprint, so a leaderboard row means one specific model and
swapping it shows as a changed bot.


================================================================================
IF YOU ARE BUILDING A BENCHMARK OF MODELS
================================================================================

Hold everything below the model still and vary `config.model` alone. The harness is
shared for exactly this reason — two bots with different loops are two harnesses
being compared, and the model is the smaller half of that difference.

Three fields decide whether two rows are comparable, and all three are recorded
in `result.json` and shown in the standings:

    harness        the version of the shared loop. Bumped when a change here
                   could move a decision
    state_view     what the model was looking at (the state_view label)
    stock_tools    whether it had the shared four or a set of its own

And one field decides whether a row is worth reading at all:

    fallback_rate  the share of turns the model did NOT decide. A call timed
                   out or came back unusable and `fallback_move` played instead,
                   so those turns are our heuristic wearing the model's name.
                   Above 0.1 the row is measuring us. Flagged in the standings.

Budget: about 30k tokens a run with the default view, so ~1.5M for a
fifty-seed entry. `state_view="json"` is 6.6x that.
"""

from __future__ import annotations

import json
from typing import Any

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig
from pokelike.core import render


class ExampleBot(LLMBot):
    name = "llm-example"

    # ========================================================================
    # 1. THE SYSTEM PROMPT      -> messages[0], role "system"
    # ========================================================================
    #
    # This is the whole submission for most LLM bots. `GAME_RULES` is the
    # factual half — trainer counts per map, what closes when you pick a node —
    # read out of the game bundle rather than guessed. Keep it and add strategy,
    # or drop it and write your own if you think the facts are what is holding
    # the model back. That is a legitimate experiment, just a different one.
    #
    # It is sent unchanged on every turn, so its cost is paid every turn.
    # Set it as `prompt=...` in `config = LLMConfig(...)` below.

    PROMPT = GAME_RULES + """
PLAY LIKE THIS
- Read the numbers you are given rather than working them out. HP is already a
  percentage and the exits are already listed; arithmetic is where you slip.
- Ask `bag` before spending a turn on an item node. A second potion is worth
  less than almost anything else that turn could buy.
- Weigh `set_lead` on every map turn. It is free — it does not consume the turn
  — and who enters the battle first decides most battles.
- Call `state_json` when something you need is genuinely not above. It costs
  about six times the rest of the message, so do not call it out of habit.

Think briefly, then call `play`. Always call `play`."""

    # ========================================================================
    # 2. THE MODEL AND HOW IT IS ASKED    -> the top-level fields of the body
    # ========================================================================

    # The model and how it is asked live in `config` below: one LLMConfig
    # for every knob, validated the moment the bot is built.

    # ========================================================================
    # 3a. TOOL DEFINITIONS      -> body["tools"]. Sent EVERY turn.
    # ========================================================================
    #
    # These schemas are prompt. The `description` you write here is what the
    # model reads to decide whether to call the thing, and it is re-sent on
    # every single turn of every single run — the four shared ones already cost
    # 1137 characters, more than the state view. Write them like prompt, because
    # they are: say what the tool gives, and say when NOT to call it, which is
    # the half people leave out and then wonder why the model calls everything.
    #
    # The shared four are always present unless you rebuild `tools()`. `play`
    # may never be removed, and that is checked when the bot is built rather
    # than discovered fifty runs in, when every turn has fallen back.
    #
    # Giving the model tools the others did not have is allowed and is recorded:
    # the standings mark the row. Not as a fault — it is a different question,
    # and the mistake would be comparing it with the rest as the same one.
    #
    # Set extra tools as `extra_tools=[...]` in `config = LLMConfig(...)` below.

    EXTRA_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "state_json",
                "description": (
                    "The raw state dict as JSON: team, bag, map, run, actions, "
                    "stats, type_items. Everything the Python bots see. Use it "
                    "when what you need is not in the summary."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "part": {
                            "type": "string",
                            "description": (
                                "one key, or 'all'. One key is far cheaper: the "
                                "whole dict is about 5900 characters."
                            ),
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "bag",
                "description": "What you are carrying, by name.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]

    # Every knob in one validated place. `render_state` is overridden below, so
    # `state_view` is ignored and gets recorded as "custom".
    config = LLMConfig(
        prompt=PROMPT,
        temperature=0.3,       # low, not zero: zero is not reproducible either
        max_tokens=900,        # a short reason plus a tool call
        max_rounds=6,          # this prompt asks for two tools before play
        memory=8,              # enough to notice it is going in circles
        token_budget=60_000,   # ~2x a normal run; hitting it ENDS the run
        state_view="screen",
        extra_tools=EXTRA_TOOLS,
    )

    # ========================================================================
    # 3b. TOOL RESULTS      -> the "tool" messages. Prompt as well.
    # ========================================================================

    def answer_tool(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
        """Answers one tool call. **What this returns is prompt.**

        It goes into the conversation as a `role: "tool"` message and stays
        there for the rest of the turn, so a tool that hands back three
        kilobytes has spent more than sending the whole state would have. That
        is why `state_json` takes a `part` and truncates: the cheap version has
        to be the easy one to call, or the model will take the expensive one.

        Two rules worth keeping. **Never raise**: an exception throws the whole
        turn away and hands it to `fallback_move`, so a model that mistypes a tool
        name costs you a decision it was about to make. And **always end with
        `super()`**, or you quietly take away the shared four while `tools()`
        still advertises them.
        """
        if name == "bag":
            return ", ".join(state.get("bag") or []) or "(carrying nothing)"

        if name == "state_json":
            part = (args or {}).get("part") or "all"
            if part != "all" and part not in state:
                return (f"no key '{part}'. There is: {', '.join(sorted(state))}")
            payload = state if part == "all" else {part: state[part]}
            text = json.dumps(payload, separators=(",", ":"))
            # Truncated on purpose: a late-run map is large, and a tool reply
            # that fills the context costs the model the reasoning it was about
            # to do. Saying it was cut beats pretending it was all there.
            return text if len(text) <= 4000 else text[:4000] + " ...(truncated)"

        return super().answer_tool(name, args, state)

    # ========================================================================
    # 4. THE VIEW      -> the first part of messages[1], role "user"
    # ========================================================================
    #
    # THE DEEPEST KNOB. Everything above changes what the model is told to do;
    # this changes what it is told. Four settings need no code at all:
    #
    #     state_view="screen"                   the rendered view    ~880 char
    #     state_view="json"                     the whole dict      ~5900 char
    #     state_view="both"                     the view, then the dict
    #     state_view=["team", "actions"]        those keys, as JSON
    #
    # What the DEFAULT leaves out, measured on a real state: the engine's
    # type -> item table (18 entries, 0 of them shown), the map edges (which node
    # leads to which — reachable through `what_lies_ahead` instead), raw
    # base_stats, item_id and item_desc, and 21 of 23 node ids. It renders what
    # a person would look at, not everything that is true.
    #
    # `render_state()` is for when none of the four fit. Below is the case worth
    # showing: taking the state and writing it out as something a model reads
    # WELL, which is not the same as what a person reads well.


    def render_state(self, state: dict[str, Any]) -> str:
        """The state as prose, with the arithmetic already done.

        Three changes from the rendered view, each with a reason:

        1. **HP as a percentage, not a bar.** `#######...` and `17/24` both make
           the model divide before it can compare two Pokemon, and division is
           where it slips. `71%` is the number it actually wanted.

        2. **The consequence stated, not drawn.** The ASCII map is a picture of
           a graph; a model has to re-derive from it that picking one node
           closes the others. Here it is a sentence, next to the options.

        3. **The exits inline.** `what_lies_ahead` exists as a tool because
           reading the edges matters, and a tool call costs a round trip. Four
           lines put it in front of the model for free — which is a real trade:
           it is cheaper, and it also removes the chance to observe whether the
           model knows to ask.

        Nothing here can break the turn: the journal and the "pick an index"
        line are added around whatever this returns.
        """
        run = state.get("run") or {}
        team = state.get("team") or []
        parts = [
            f"TURN {state.get('steps', 0)} — map {run.get('map', 0)}, "
            f"{run.get('badges', 0)} badges, {len(team)} Pokemon alive."
        ]

        if team:
            parts += ["", "YOUR TEAM"]
            for i, p in enumerate(team):
                pct = f"{p['hp'] / p['max_hp']:.0%}" if p.get("max_hp") else "?"
                types = "/".join(p.get("types") or []) or "?"
                move = p.get("move") or {}
                lead = "   <- LEADS THE NEXT BATTLE" if i == 0 else ""
                parts.append(
                    f"  {i}. {p['name']:<12} Lv{p.get('level', '?'):<3} "
                    f"{pct:>4} HP  {types:<14} "
                    f"{move.get('name', '-')} {move.get('power', '')}{lead}"
                )

        bag = state.get("bag") or []
        parts += ["", f"CARRYING: {', '.join(bag) if bag else 'nothing'}"]

        parts += ["", "YOUR OPTIONS"]
        exits = self._exits_by_action(state)
        for i, a in enumerate(state.get("actions") or []):
            what = a.get("node") or a.get("label", "")
            after = exits.get(i)
            tail = f"  — then you could reach: {after}" if after else ""
            parts.append(f"  [{i}] {what}{tail}")
        if len(state.get("actions") or []) > 1 and state.get("screen") == "map-screen":
            parts.append("  Taking one of these closes the others for good.")

        return "\n".join(parts)

    @staticmethod
    def _exits_by_action(state: dict[str, Any]) -> dict[int, str]:
        """Which node kinds each option leads to, read off the map's edges."""
        m = state.get("map")
        if not m:
            return {}
        by_id = {n["id"]: n for n in m["nodes"]}
        out = {}
        for i, a in enumerate(state.get("actions") or []):
            if a.get("kind") != "node":
                continue
            after = sorted({by_id[t]["kind"]
                            for f, t in m["edges"] if f == a.get("id") and t in by_id})
            if after:
                out[i] = ", ".join(after)
        return out

    # ========================================================================
    # 5. WHEN THE MODEL DOES NOT ANSWER
    # ========================================================================

    def fallback_move(self, state: dict[str, Any]) -> int:
        """Heal if someone is hurt, else widen the team, else the first option.

        The same shape as the harness default, spelled out so the file shows
        where the hook is. **Overriding this is rarely wise**: whatever it does
        is played under your bot's name on every turn the model did not answer,
        and `fallback_rate` reports the share. A clever fallback is cleverness
        being measured as though the model produced it.
        """
        actions = state["actions"]
        team = state.get("team") or []
        hurt = any(p["hp"] / p["max_hp"] < 0.4 for p in team if p.get("max_hp"))
        for want in (("pokecenter",) if hurt else ()) + ("catch", "pokecenter"):
            for i, a in enumerate(actions):
                if a.get("node") == want:
                    return i
        return 0

    # ========================================================================
    # 6. THE MODEL ITSELF — the one hook this file does NOT use
    # ========================================================================
    #
    # `call_model(messages) -> message dict` is the whole of the network.
    # Override it and the loop, the tools, the journal and the fallback policy
    # above it keep working unchanged. That is where a model that is not an HTTP
    # endpoint goes:
    #
    #     def call_model(self, messages):
    #         out = my_local_model.chat(messages, tools=self.tools())
    #         self.calls += 1
    #         self.tokens_used += out.usage.total          # keep the counters
    #         return {"content": out.text, "tool_calls": out.tool_calls}
    #
    # Return the OpenAI-shaped `message`: `content`, and `tool_calls` as
    # `[{"id", "function": {"name", "arguments"}}]` with `arguments` a JSON
    # STRING. Raise LLMConfigError for anything that will fail identically
    # forever, LLMError for anything transient — the first ends the run, the
    # second falls back and is counted.
    #
    # A Hugging Face model reaches the harness three ways: the Inference API and
    # Inference Endpoints are OpenAI-compatible, so they need no code at all;
    # your own fine-tune behind vLLM or TGI is the same; and a local checkpoint
    # goes here. For the third, pin the repo id AND a commit sha in this file
    # rather than a branch, or the model moves under a row that claims it.

    # ========================================================================
    # 7. WHAT GETS RECORDED
    # ========================================================================

    def reason(self) -> str:
        """One line under each decision in `-d` logs.

        The harness fills `_last_why` with the model's own stated reason, or
        with why the turn fell back.
        """
        return f"[example] {super().reason()}"

    def metadata(self) -> dict[str, Any]:
        """Into the run registry and into `result.json`.

        The base already records model, harness, state_view, stock_tools, calls,
        turns, tokens, fallbacks and fallback_rate. Add what your bot varies
        that nothing else knows about.

        **Never the token or the endpoint.** `stats/` is gitignored, but
        `result.json` is committed, and a result file is exactly the kind of
        thing that gets pasted into an issue.
        """
        return {**super().metadata(),
                "extra_tools": [t["function"]["name"] for t in self.cfg.extra_tools]}
