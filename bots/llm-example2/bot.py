"""llm-example2: everything harness generation 2 can do, one small thing at a time.

    uv run pokelike bot run --bot llm-example2 --runs 1 -ddd

Credentials come from `.env` at the repository root, so nothing goes on the command line.

A reference, not a contender. It changes everything at once, which shows the surface
and ruins the score. Not benchmarked. Copy the parts you want.

What one turn looks like:

    system         your prompt
    (kept turns)   the last few, its own words and the tool answers
    user           the state now, plus its notes, its plan, and the journal
    tools          sent beside the messages, every turn, called or not

Four memories, four lifetimes:

    scratch_turns   whole turns kept          dies with the run
    memory          one line per past turn    dies with the run
    plan_chars      its route for this map    dies with the map
    notes_cap       notes it writes itself    CROSSES runs
"""

from __future__ import annotations

from typing import Any

from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig, tool
from pokelike.core import render


class Example2Bot(LLMBot):
    name = "llm-example2"

    # ---------------------------------------------------------------- 1. the prompt
    # GAME_RULES is the factual half. Added here: how to use its memory. A model
    # given a notebook and not told to keep it will use it twice and forget it.

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
    # @tool is the whole declaration: the name comes from the method, the parameters
    # from the signature. The description is prompt, so say when NOT to call it too.

    @tool("Whether your team is healthy enough for a fight, and whether a pokecenter "
          "is reachable. One line. Call it before a battle, not on every screen.")
    def risk_check(self, state: dict[str, Any]) -> str:
        """In: the state. Out: one line about the team's health."""
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

    @tool("Which of YOUR move types are super effective against a type you name, so "
          "you can pick a lead. Only useful once a tooltip told you what you face.",
          against="the defending type, one word")
    def beats(self, state: dict[str, Any], against: str) -> str:
        """In: the state and a type name. Out: which slots answer it."""
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

    # A bot may carry its own knowledge. The state does not contain this.
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
    # A generation-2 bot is mostly this block. None of it needs code.

    config = LLMConfig(
        prompt=PROMPT,

        temperature=0.3,        # low, not zero: zero is not reproducible either
        max_tokens=1200,        # a paragraph, a plan, and a play call
        max_rounds=6,           # this prompt asks for two or three tools before play
        retries=5,              # a 429 is not the model's fault, so try again
        token_budget=80_000,    # about 3x a normal run. Hitting it ENDS the run,
                                # on purpose: a runaway loop should stop, not creep

        state_view="screen",    # IGNORED HERE: section 4 replaces render_state, which is
                                # the only thing that reads this. "json" is 6x the tokens

        memory=12,              # journal lines. -1 keeps every turn
        scratch_turns=3,        # whole turns kept. -1 keeps all, and costs about 5x
        scratch_state="brief",  # IGNORED HERE: section 5 replaces render_scratch.
                                # line (a marker), brief (facts), full (the old screen)
        notes_cap=12,           # notes it may hold. 0 turns the notebook off
        note_chars=200,         # longer notes are cut, not refused
        cross_run_memory=True,  # the point of generation 2: notes outlive the run
        keep_across_regions=("notes",),   # what crosses into the NEXT region. The plan and
                                          # the kept turns are about a map that will not
                                          # exist there; a lesson might still hold
        plan_chars=600,         # room for a route that names its nodes

        bag_tool=True,          # a shared tool now, no code needed
        # `what_lies_ahead` is the tool that says where each option leads. Section 4
        # already prints that in the view, every turn, for free: keeping the tool too
        # would be a round trip for something already on the screen.
        drop_tools=("what_lies_ahead",),
    )

    # ------------------------------------------------------------------- 4. the view
    def render_state(self, state: dict[str, Any]) -> str:
        """In: the state. Out: the text of this turn's user message."""
        # REPLACES the built-in view, so `state_view` above is set but has no effect:
        # it is the setting the built-in one reads, and this does not call it.
        # HP as a percentage, because the model should not have to divide. Exits
        # inline, because asking for them costs a round trip.
        run = state.get("run") or {}
        team = state.get("team") or []
        # The region goes here when it is not Kanto, exactly as the built-in view does
        # it. Replacing the view means inheriting the job of saying WHERE you are: the
        # built-in one carries the region in every mode it has, and a custom line that
        # leaves it out is a model playing Johto believing it is in Kanto.
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
        """In: the state of a turn being kept. Out: the one line it shows."""
        # REPLACES the built-in one, so `scratch_state` above is set but has no
        # effect, for the same reason as `state_view`. The old screen is not sent
        # again: it is stale, and the current one is in the fresh message. Only what
        # changed is worth a line.
        run = state.get("run") or {}
        team = state.get("team") or []
        low = min((p["hp"] / p["max_hp"] for p in team if p.get("max_hp")), default=1.0)
        return (f"[turn {state.get('steps')}: {state.get('screen')}, "
                f"map {run.get('map', 0)}, {run.get('badges', 0)} badges, "
                f"{len(team)} alive, weakest at {low:.0%}]")

    # ----------------------------------------------------------- 6. between regions
    def region_cleared(self, done: dict[str, Any]) -> str | None:
        """In: the region result. Out: what the next region opens with."""
        # Called with the memory STILL INTACT, which is what makes this possible: the
        # model reads its own journal and its last exchanges and writes the summary
        # itself, instead of taking ours. The forgetting happens after this returns.
        try:
            # The ASK GOES LAST. With it in the system message the model answered by
            # repeating it back, summary and instruction in one paragraph, which is
            # what then reached the next region. A model looks for the task in the
            # last user turn, so that is where it belongs, with the memory as context.
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
            ], tools=[])       # prose, not a tool call: with tools attached it plays
            return (reply.get("content") or "").strip() or super().region_cleared(done)
        except Exception:      # noqa: BLE001
            # A summary is a nicety: a failed call must not end a campaign that is
            # going well. Fall back to the standard sentence.
            return super().region_cleared(done)

    # -------------------------------------------------------------- 7. what is filed
    def add_metadata(self) -> dict[str, Any]:
        """In: nothing. Out: my own facts, written beside the score."""
        # Only what nothing else could know. The model, the harness generation, the
        # view and whether the tools are the stock set are already recorded.
        return {"tuned_for": "gemini-class models", "notes_policy": "one per run"}
