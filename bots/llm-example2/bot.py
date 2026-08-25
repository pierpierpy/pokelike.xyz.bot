"""The `llm-example2` bot shows everything harness generation 2 can do, one
setting at a time.

    uv run pokelike bot run --bot llm-example2 --runs 1 -ddd

Credentials come from `.env` at the repository root, so nothing goes on the
command line.

This bot is a reference. It turns on every optional feature at once so each one
is easy to see, which is a bad setup for an actual run. It is not benchmarked.
Copy the parts you want.

What one turn looks like:

    system         your prompt
    (kept turns)   the last few, its own words and the tool answers
    user           the state now, plus its notes, its plan, and the journal
    tools          sent beside the messages, every turn, called or not

Four memories with four lifetimes:

    scratch_turns   whole turns kept          dies with the run
    memory          one line per past turn    dies with the run
    plan_chars      its route for this map    dies with the map
    notes_cap       notes it writes itself    crosses runs
"""

from __future__ import annotations

from typing import Any

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig, tool
from pokelike.core import render


class Example2Bot(LLMBot):
    name = "llm-example2"

    # ---------------------------------------------------------------- 1. the prompt
    # The GAME_RULES constant provides the factual half. This prompt adds instructions
    # for using the notebook and plan.

    PROMPT = GAME_RULES + """
YOUR MEMORY IS PART OF PLAYING

  - NOTES cross runs. They are the only thing that survives losing. Write one the
    moment you learn something: the run stops the instant your last Pokemon faints.
  - the PLAN is this map's route. Write it before your first choice here, and name
    the nodes in it.
  - your LAST FEW TURNS come with you in full. Read them instead of working the same
    thing out twice.
  - the JOURNAL is one line per earlier turn. Older, shorter, still useful.

A note worth keeping carries a number or a name:
  good  "map 0 trainers are safe with a level 8 lead"
  bad   "be careful with trainers"        nothing changes because of it
  bad   "I am on map 1"                   false in a minute

FOUR REGIONS
Kanto, Johto, Hoenn and Sinnoh. Each is a whole game: a new starter, eight of its own
gyms, its own Elite Four, badges from zero. Only your NOTES cross a boundary, so a note
about Brock is worth nothing in Johto while "heal before every gym" is worth something
everywhere. Write the second kind.

The turn ENDS at `play`, so anything called after it is thrown away. Call `plan`,
`remember` and the rest FIRST, `play` last.

Think briefly, then call `play`. Always call `play`."""

    # ------------------------------------------------------------- 2. its own tools
    # The @tool decorator handles the whole declaration. The name comes from the
    # method, and the parameters come from the signature. The description is prompt
    # text, so state when not to call the tool as well.

    @tool("Whether your team is healthy enough for a fight, and whether a pokecenter is reachable. One line. Call it before a battle, not on every screen.")
    def risk_check(self, state: dict[str, Any]) -> str:
        """Return one line about the team's health given the current state."""
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

    @tool("Which of YOUR move types are super effective against a type you name, so you can pick a lead. Only useful once a tooltip told you what you face.", against="the defending type, one word")
    def beats(self, state: dict[str, Any], against: str) -> str:
        """Return which team slots have a super-effective move against the named type."""
        want = against.strip().lower()
        if want not in self.STRONG_AGAINST:
            return f"'{against}' is not a type. Try: {', '.join(sorted(self.STRONG_AGAINST))}."
        good = [f"[{i}] {p['name']} ({((p.get('move') or {}).get('type') or '').lower()})"
                for i, p in enumerate(state.get("team") or [])
                if want in self.STRONG_AGAINST.get(
                    ((p.get("move") or {}).get("type") or "").lower(), ())]
        if not good:
            return f"nothing beats {want}. Lead with your healthiest instead."
        return (f"super effective against {want}: {', '.join(good)}. "
                f"`set_lead` is free, so put one in slot 0 first.")

    # A bot may carry its own knowledge. The state does not contain this table.
    STRONG_AGAINST = {
        "normal": set(), "fire": {"grass", "bug", "ice", "steel"},
        "water": {"fire", "ground", "rock"}, "grass": {"water", "ground", "rock"},
        "electric": {"water", "flying"}, "ice": {"grass", "ground", "flying", "dragon"},
        "fighting": {"normal", "rock", "steel", "ice", "dark"},
        "poison": {"grass", "fairy"},
        "ground": {"fire", "electric", "poison", "rock", "steel"},
        "flying": {"grass", "fighting", "bug"}, "psychic": {"fighting", "poison"},
        "bug": {"grass", "psychic", "dark"}, "rock": {"fire", "ice", "flying", "bug"},
        "ghost": {"psychic", "ghost"}, "dragon": {"dragon"},
        "dark": {"psychic", "ghost"}, "steel": {"ice", "rock", "fairy"},
        "fairy": {"dragon", "dark", "fighting"},
    }

    # ------------------------------------------------------------------ 3. the knobs
    # A generation-2 bot is mostly this block. None of these settings need code.

    config = LLMConfig(
        prompt=PROMPT,

        # model=None,           # the model comes from --model or $MODEL_ID, and a bot
        #                       # folder hardcoding one would fix what it is measured with
        temperature=0.3,        # low but not zero, because zero is not reproducible
        reasoning_effort="low", # the model reasons before answering, and "none" turns reasoning off
        max_tokens=100_000,     # High enough that a model which reasons is never cut off,
                                # since the longest reply recorded here runs to about 33k
                                # tokens. It stops there because a provider refuses a value
                                # above what its own model can produce, and a refused call
                                # ends the run.
        max_rounds=6,           # this prompt asks for two or three tools before play
        retries=5,              # a 429 is not the model's fault, so try again
        token_budget=1_000_000_000,    # about 3x a normal run, and hitting the budget ends
                                # the run on purpose to stop runaway loops

        # state_view="screen",    # ignored here because section 4 replaces render_state, which
        #                         # is the only thing that reads this setting. "json" is 6x the tokens

        memory=12,              # journal lines, and -1 keeps every turn
        scratch_turns=3,        # whole turns kept, and -1 keeps all at about 5x the cost
        # scratch_state="brief",  # ignored here because section 5 replaces render_scratch.
        #                         # Options are line (a marker), brief (facts), full (the old screen)
        notes_cap=10000,           # max note storage, and 0 turns the notebook off
        note_chars=100000,         # longer notes are truncated silently
        cross_run_memory=True,  # notes outlive the run when this is True
        keep_across_regions=("notes",),   # what crosses into the next region. The plan
                                          # and kept turns describe a map that will not
                                          # exist there, but a general lesson might hold.
        plan_chars=1000000,         # this gives room for a route that names its nodes

        run_summary="brief",    # what a finished run tells the next one: none, line or
                                # brief. Section 7 replaces render_run_summary, so this
                                # value is only what is used when the model does not answer
        run_summary_keep=10,    # how many finished runs the model still hears about
        run_summary_chars=1200, # the budget per run, told to the model and then enforced

        bag_tool=True,          # this enables a shared tool that needs no code
        # extra_tools=[],       # raw tool dicts, for a tool with no method behind it.
        #                       # Section 2 uses the @tool decorator instead, which writes
        #                       # the schema from the signature and wires the method up
        # The `what_lies_ahead` tool reports where each option leads. Section 4 already
        # prints that in the view every turn for free, so the tool would just be a
        # redundant round trip.
        drop_tools=("what_lies_ahead",),
    )

    # ------------------------------------------------------------------- 4. the view
    def render_state(self, state: dict[str, Any]) -> str:
        """Return the text that forms this turn's user message from the given state."""
        # This method replaces the built-in view, so `state_view` above has no effect.
        # HP as a percentage, exits inline to avoid a tool round trip.
        run = state.get("run") or {}
        team = state.get("team") or []
        # Include the region when it is not Kanto, matching the built-in view.
        where = state.get("region") or "kanto"
        out = [f"TURN {state.get('steps', 0)}   map {run.get('map', 0)}   "
               f"{run.get('badges', 0)} badges   {len(team)} alive"
               + (f"   region: {where}" if where != "kanto" else "")]

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
        # One call instead of walking the map's edges by hand.
        exits = render.exits_of(state, unique=True)
        for i, a in enumerate(state.get("actions") or []):
            tip = f"  ({a['tooltip']})" if a.get("tooltip") else ""
            after = f"  -> then: {', '.join(exits[i])}" if exits.get(i) else ""
            out.append(f"  [{i}] {a.get('node') or a.get('label', '')}{tip}{after}")
        if state.get("screen") == "map-screen" and len(state.get("actions") or []) > 1:
            out.append("  Picking one closes the others on this layer for good.")
        return "\n".join(out)

    # ------------------------------------------------------- 5. a kept turn's slot
    def render_scratch(self, state: dict[str, Any]) -> str:
        """Return the one-line summary shown for a kept turn's state."""
        # This method replaces the built-in render, so `scratch_state` above has no effect.
        # Only what changed is worth a line, because the current screen is in the fresh message.
        run = state.get("run") or {}
        team = state.get("team") or []
        low = min((p["hp"] / p["max_hp"] for p in team if p.get("max_hp")), default=1.0)
        return (f"[turn {state.get('steps')}: {state.get('screen')}, "
                f"map {run.get('map', 0)}, {run.get('badges', 0)} badges, "
                f"{len(team)} alive, weakest at {low:.0%}]")

    # ----------------------------------------------------------- 6. between regions
    def region_cleared(self, done: dict[str, Any]) -> str | None:
        """Return a summary for the next region to open with, based on the completed region's result."""
        # The runner calls this method with the memory still intact, so the model
        # can read its own journal and write the summary itself. The forgetting
        # happens after this method returns.
        try:
            reply = self.call_model([
                {"role": "system", "content":
                    "You are playing a Pokemon roguelike, one region at a time."},
                *self.memory_messages(),
                {"role": "user", "content":
                    f"{self.memory_text()}\n\n"
                    f"You cleared {done['region']} with {done['badges']} badges. Next is "
                    f"{done['next']}: a new starter, new gyms, badges from zero, and only "
                    f"your notes come with you. Write at most five short lines of what you "
                    f"learned that will STILL BE TRUE there. No preamble, just the lines."},
            ], tools=[])       # prose only, not a tool call
            return (reply.get("content") or "").strip() or super().region_cleared(done)
        except Exception:      # noqa: BLE001
            # A failed summary must not end a campaign that is going well.
            return super().region_cleared(done)

    # ------------------------------------------------- 7. what a finished run leaves
    def render_run_summary(self, state: dict[str, Any],
                           score: dict[str, Any] | None) -> str:
        """Return what this run should tell the next one, written by the model itself."""
        # The runner calls this once the run is over, through `finish`, and whatever
        # comes back is shown at every turn of every later run, next to the notes.
        # The default levels ("line" and "brief") state the figures. Here the model
        # is asked instead, so the entry says what it thinks went wrong rather than
        # what happened, and the entries accumulate into an account of its own play.
        #
        # Read `self.last_seen` and not `state`: the engine empties its state at game
        # over, so `state` arrives with no team and no badges however far it got.
        seen = self.last_seen or {}
        run = seen.get("run") or {}
        budget = self.cfg.run_summary_chars
        try:
            reply = self.call_model([
                {"role": "system", "content":
                    "You are playing a Pokemon roguelike, one run at a time."},
                {"role": "user", "content":
                    f"{self.memory_text()}\n\n"
                    f"That run is over. Seed {self.seed}, {run.get('badges', 0)} "
                    f"badges, {self.turns} turns, and you got as far as map "
                    f"{run.get('map', 0)}. In under {budget} characters, say what you "
                    f"would do differently, and be concrete about the decision that "
                    f"cost you rather than general about strategy. This is the only "
                    f"thing the next run will know about this one."},
            ], tools=[])       # prose, so no tool is offered
            said = (reply.get("content") or "").strip()
            # Falling back to the figures is better than leaving the run unaccounted
            # for, and `finish` cuts whatever comes back to the budget anyway.
            return said or super().render_run_summary(state, score)
        except Exception:      # noqa: BLE001
            # A failed summary must not end a run that has already been played.
            return super().render_run_summary(state, score)

    # -------------------------------------------------------------- 8. what is filed
    def add_metadata(self) -> dict[str, Any]:
        """Return bot-specific metadata to record beside the score."""
        # This records only what nothing else could know. The model, harness
        # generation, view, and stock-tools flag are already recorded elsewhere.
        return {"tuned_for": "gemini-class models", "notes_policy": "one per run"}
