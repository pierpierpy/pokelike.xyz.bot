"""llm-example2: everything generation 2 added, one small useful change at a time.

    uv run pokelike bot run --bot llm-example2 --runs 1 -ddd

Credentials come from `.env` at the repository root (gitignored, and the container
reads it too), so nothing needs to go on the command line.

**A reference, not a contender.** Like [llm-example](../llm-example/), it moves
everything at once, which is the right way to show the surface and the wrong way to
learn from a score. It is not benchmarked. Copy the parts you want.

The difference between the two files is the harness generation. `llm-example` shows
`HARNESS = 1`: a system prompt, one user message, four tools. This one shows
`HARNESS = 2`, which added the three things a model needs to get better at a game
rather than merely play it:

    a NOTEBOOK it writes and edits itself, which can outlive the run
    a PLAN for the map, shown back every turn until it replaces it
    a SCRATCHPAD of whole turns, so it reads its own words rather than a summary

================================================================================
WHAT ONE TURN LOOKS LIKE NOW
================================================================================

    {
      "model": ..., "temperature": ..., "max_tokens": ...,
      "tools": [ ... ],                 <- BESIDE the messages, not inside them.
                                           This is why a conversation log does
                                           not show them. Sent every turn,
                                           called or not: a tool is prompt
      "messages": [
        {"role": "system"},             <- config.prompt
        ---- the scratchpad, config.scratch_turns of these ----
        {"role": "user"},               <- what config.scratch_state puts here
        {"role": "assistant"},          <- ITS OWN WORDS, the reason it is kept
        {"role": "tool"},               <- and what the tools answered
        ---- then this turn ----
        {"role": "user"}                <- the state NOW, plus the notes, plus
                                           the plan, plus the journal
      ]
    }

Four memories, four lifetimes, and knowing which is which is most of using this:

    scratchpad   whole turns, verbatim        config.scratch_turns   dies with the run
    journal      one line per past turn       config.memory          dies with the run
    plan         one paragraph, its own       config.plan_chars      dies with the map
    notes        numbered, it edits them      config.notes_cap       CROSSES runs

================================================================================
THE COST OF EACH, MEASURED
================================================================================

Everything below is a real number from a real trace, not an estimate:

    the system prompt                   1,263 char, every turn
    the four shared tool schemas        1,137 char, every turn, called or not
    the rendered state                    831 char, every turn
    a kept scratchpad turn              ~1,000 char each ("line" mode)
      the same turn with the screen     ~2,200 char each ("full" mode), which
                                        v5 measured at 269k input tokens for ONE
                                        run against 41k: six and a half times
    a note                              up to config.note_chars, every turn

So `scratch_turns=-1` (keep everything) on a ninety-decision run ends up carrying
about 22k tokens in its last request and a million across the run, against 200k
with three turns kept. Affordable, and worth knowing before setting it.
"""

from __future__ import annotations

from typing import Any

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig, tool
from pokelike.core import render


class Example2Bot(LLMBot):
    name = "llm-example2"

    # =====================================================================
    # 1. THE PROMPT, which is still the submission
    # =====================================================================
    #
    # `GAME_RULES` is the factual half: what the node types are, that picking one
    # closes the rest of the layer, how many Pokemon a trainer carries per map.
    # Added here is only what generation 2 makes possible, and it is written as
    # instructions about ITS OWN MEMORY, because a model given a notebook and not
    # told to run it will call `remember` twice and then forget it exists.

    PROMPT = GAME_RULES + """
YOUR MEMORY IS PART OF PLAYING

You have four kinds of memory and they are not interchangeable:
  - your NOTES cross runs. They are the only thing that survives losing. Write a
    note the moment a run teaches you something, not at the end: there is no end
    to write at, the run stops the instant your last Pokemon faints.
  - your PLAN is this map's route. Write it before your first choice on a map,
    while every option is still open, and name the nodes in it.
  - your LAST FEW TURNS come with you in full, your own words included. Read them
    instead of working the same thing out twice.
  - the JOURNAL is one line per earlier turn. Older, shorter, still useful.

A note worth its space carries a number or a name:
  good  "map 0 trainers are safe with a level 8 lead"
  good  "skipping the pokecenter before the gym lost me 3 runs at exactly 1 badge"
  bad   "be careful with trainers"      no number, so no decision changes
  bad   "I am on map 1"                 false in a minute

Two things to have done before this run ends, and you cannot know which turn is
the last: a `plan` for the map you are on, and one `remember` or `revise`.

ORDER YOUR CALLS. The turn ENDS at `play`, so anything you call after it in the
same message is discarded. Call `plan`, `remember`, `revise` and `forget` FIRST,
then `play` last.

Think briefly, then call `play`. Always call `play`."""

    # =====================================================================
    # 2. TWO TOOLS OF ITS OWN, declared with @tool
    # =====================================================================
    #
    # A tool is two prompt surfaces: its SCHEMA, re-sent every turn whether called
    # or not, and its ANSWER. The @tool decorator derives name, schema and dispatch
    # from one definition: no hand-written JSON, no config line wiring it in, no
    # branch in answer_tool. Say when NOT to call a tool, which is the half people
    # leave out and then wonder why the model calls everything.

    # Enough of the chart to answer the beats tool. A bot may carry its own
    # knowledge: this is data the state does not contain, and the model knowing it
    # anyway is fine, being able to check it against ITS OWN team is the point.
    STRONG_AGAINST = {
        "normal": set(), "fire": {"grass", "bug", "ice", "steel"},
        "water": {"fire", "ground", "rock"}, "grass": {"water", "ground", "rock"},
        "electric": {"water", "flying"}, "ice": {"grass", "ground", "flying", "dragon"},
        "fighting": {"normal", "rock", "steel", "ice", "dark"},
        "poison": {"grass", "fairy"}, "ground": {"fire", "electric", "poison", "rock", "steel"},
        "flying": {"grass", "fighting", "bug"}, "psychic": {"fighting", "poison"},
        "bug": {"grass", "psychic", "dark"}, "rock": {"fire", "ice", "flying", "bug"},
        "ghost": {"psychic", "ghost"}, "dragon": {"dragon"},
        "dark": {"psychic", "ghost"}, "steel": {"ice", "rock", "fairy"},
        "fairy": {"dragon", "dark", "fighting"},
    }

    @tool("Whether your team is healthy enough for a fight, and whether "
          "a pokecenter is reachable from here. One line. Call it before "
          "a battle node, not on every screen.")
    def risk_check(self, state) -> str:
        """Team health and whether healing is reachable, in one line.

        In: the state. Out: a sentence the model can act on.
        """
        team = state.get("team") or []
        if not team:
            return "no team yet."
        hurt = [f"{p['name']} {p['hp']}/{p['max_hp']}"
                for p in team if p.get("max_hp") and p["hp"] / p["max_hp"] < 0.5]
        heal = any((a.get("node") or "") == "pokecenter"
                   for a in (state.get("actions") or []))
        return (f"{len(team)} alive. "
                + (f"below half: {', '.join(hurt)}. " if hurt else "all above half. ")
                + ("a pokecenter is one of your options now."
                   if heal else "no pokecenter among your options."))

    @tool("Which of YOUR team's move types are super effective against a "
          "type you name, so you can pick a lead. Give the defending type, "
          "for example 'rock'. Only useful when a tooltip told you what "
          "you are about to fight.",
          against="the defending type, one word")
    def beats(self, state, against: str) -> str:
        """Which of the team's move types are super effective against a type.

        In: the state and the defending type. Out: the slots that answer it.
        """
        want = against.strip().lower()
        if want not in self.STRONG_AGAINST:
            return (f"'{against}' is not a type I know. Try one of: "
                    f"{', '.join(sorted(self.STRONG_AGAINST))}.")
        good = []
        for i, p in enumerate(state.get("team") or []):
            mtype = ((p.get("move") or {}).get("type") or "").lower()
            if mtype and want in self.STRONG_AGAINST.get(mtype, ()):
                good.append(f"[{i}] {p['name']} ({mtype})")
        if not good:
            return (f"nothing on your team is super effective against {want}. "
                    f"Lead with your healthiest instead.")
        return (f"super effective against {want}: {', '.join(good)}. "
                f"`set_lead` is free, so put one of them in slot 0 before the fight.")

    # =====================================================================
    # 3. EVERY KNOB, EXPLICITLY, WITH THE REASON
    # =====================================================================
    #
    # A generation-2 bot is mostly this block. Nothing here needs code.

    config = LLMConfig(
        prompt=PROMPT,

        # --- the model and how it is asked
        temperature=0.3,        # low, not zero: zero is not reproducible either
        max_tokens=1200,        # a paragraph of thought, a plan, and a play call
        max_rounds=6,           # this prompt asks for two or three tools before play
        retries=4,              # attempts on a 429 or a 5xx, which are not the model's fault

        # --- what it sees
        state_view="screen",    # ignored here, `render_state` is overridden below

        # --- the four memories
        memory=12,              # journal lines. -1 keeps every turn of the run
        scratch_turns=3,        # whole turns kept. -1 keeps them all, and costs 5x
        scratch_state="brief",  # what a kept turn shows instead of its old screen:
                                # "line" is a marker, "brief" is one line of facts,
                                # "full" is the whole screen at 6.5x the tokens.
                                # "brief" is picked here so the model can watch HP
                                # fall across the turns it is holding
        notes_cap=12,           # notes it may hold. 0 turns the notebook off
        note_chars=160,         # per note; longer ones are truncated, not refused
        cross_run_memory=True,  # THE POINT OF GENERATION 2: notes outlive the run
        plan_chars=600,         # room for a route that names its nodes

        # --- tools
        bag_tool=True,
        # The symmetric half of @tool: `render_state` below already prints where each
        # option leads, so `what_lies_ahead` would be a round trip to learn something
        # already on the screen, and its schema costs tokens every turn regardless.
        # A real trade, not a free win: it also removes the chance to observe whether
        # a model knows to ask before closing a door.
        drop_tools=("what_lies_ahead",),          # a shared tool now, no code needed
        # No extra_tools needed: @tool-decorated methods above provide the schemas
        # and dispatch automatically.
    )

    # =====================================================================
    # 5. THE VIEW, and the new seam beside it
    # =====================================================================

    def render_state(self, state: dict[str, Any]) -> str:
        """The state with the arithmetic already done.

        In: the state. Out: the text of the current turn's user message.
        """
        # HP as a percentage rather than a bar and a fraction: `71%` is the number
        # the model wanted, and division is where it slips. The exits are inline
        # because reading them matters and a tool call costs a round trip. The
        # journal, the notes, the plan and the "pick an index" line are added
        # around whatever this returns, so nothing here can cost the bot its
        # memory.
        run = state.get("run") or {}
        team = state.get("team") or []
        out = [f"TURN {state.get('steps', 0)}   map {run.get('map', 0)}   "
               f"{run.get('badges', 0)} badges   {len(team)} alive"]

        if team:
            out += ["", "TEAM (slot 0 leads the next battle)"]
            for i, p in enumerate(team):
                pct = f"{p['hp'] / p['max_hp']:.0%}" if p.get("max_hp") else "?"
                move = p.get("move") or {}
                stab = " STAB" if (move.get("type") or "") in (p.get("types") or []) else ""
                out.append(
                    f"  [{i}] {p['name']:<12} Lv{p.get('level', '?'):<3} {pct:>4} HP  "
                    f"{'/'.join(p.get('types') or []) or '?':<14}"
                    f"{move.get('name', '-')} {move.get('power', '')} "
                    f"{(move.get('type') or '').lower()}{stab}")

        out += ["", "OPTIONS"]
        exits = self._exits(state)
        for i, a in enumerate(state.get("actions") or []):
            tip = f"  ({a['tooltip']})" if a.get("tooltip") else ""
            after = f"  -> then: {exits[i]}" if exits.get(i) else ""
            out.append(f"  [{i}] {a.get('node') or a.get('label', '')}{tip}{after}")
        if state.get("screen") == "map-screen" and len(state.get("actions") or []) > 1:
            out.append("  Picking one closes the others on this layer for good.")
        return "\n".join(out)

    @staticmethod
    def _exits(state: dict[str, Any]) -> dict[int, str]:
        """Which node kinds each option leads to, read off the map's edges."""
        m = state.get("map")
        if not m:
            return {}
        by_id = {n["id"]: n for n in m["nodes"]}
        out: dict[int, str] = {}
        for i, a in enumerate(state.get("actions") or []):
            if a.get("kind") != "node":
                continue
            after = sorted({by_id[t]["kind"] for f, t in m["edges"]
                            if f == a.get("id") and t in by_id})
            if after:
                out[i] = ", ".join(after)
        return out

    def render_scratch(self, state: dict[str, Any]) -> str:
        """What a KEPT turn shows where its screen used to be.

        In: the state of the turn being kept. Out: one line.
        """
        # The new seam of generation 2. The slot cannot be dropped (an assistant
        # message must follow a user one) but its content is a judgement, so it is
        # overridable. `scratch_state="brief"` would already give a decent line;
        # this one is narrower on purpose: only what CHANGED, since the current
        # screen is right there in the fresh message and a stale one invites
        # reasoning about a map that has moved on.
        run = state.get("run") or {}
        team = state.get("team") or []
        alive = f"{len(team)} alive" if team else "no team"
        low = min((p["hp"] / p["max_hp"] for p in team if p.get("max_hp")), default=1.0)
        return (f"[turn {state.get('steps')}: {state.get('screen')}, "
                f"map {run.get('map', 0)}, {run.get('badges', 0)} badges, "
                f"{alive}, weakest at {low:.0%}]")

    # =====================================================================
    # 6. WHAT IS RECORDED
    # =====================================================================

    def metadata(self) -> dict[str, Any]:
        # with this we just add some metadata.
        # Nothing is added here on purpose, and that is the lesson: the base already
        # records the model, the harness generation, the view, whether the tool set is
        # the stock one (it is not, and `stock_tools` says so by itself), the counters,
        # the notes kept and the plan held. Override this ONLY for a knob of your own
        # that nothing else could know, such as a threshold you tuned. NEVER the token
        # or the endpoint: a result file is the kind of thing that gets pasted into an
        # issue.
        return super().metadata()
