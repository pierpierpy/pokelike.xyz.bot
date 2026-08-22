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
        retries=4,              # a 429 is not the model's fault

        state_view="screen",    # ignored: render_state is overridden below

        memory=12,              # journal lines. -1 keeps every turn
        scratch_turns=3,        # whole turns kept. -1 keeps all, and costs about 5x
        scratch_state="brief",  # what a kept turn shows: line, brief, or full.
                                # brief lets it watch HP fall across those turns
        notes_cap=12,           # notes it may hold. 0 turns the notebook off
        note_chars=160,         # longer notes are cut, not refused
        cross_run_memory=True,  # the point of generation 2: notes outlive the run
        plan_chars=600,         # room for a route that names its nodes

        bag_tool=True,          # a shared tool now, no code needed
        # render_state already prints where each option leads, so this tool would be
        # a round trip for something already on the screen.
        drop_tools=("what_lies_ahead",),
    )

    # ------------------------------------------------------------------- 4. the view
    def render_state(self, state: dict[str, Any]) -> str:
        """In: the state. Out: the text of this turn's user message."""
        # HP as a percentage, because the model should not have to divide. Exits
        # inline, because asking for them costs a round trip.
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
        exits = render.exits_of(state, unique=True)
        for i, a in enumerate(state.get("actions") or []):
            tip = f"  ({a['tooltip']})" if a.get("tooltip") else ""
            after = f"  -> then: {', '.join(exits[i])}" if exits.get(i) else ""
            out.append(f"  [{i}] {a.get('node') or a.get('label', '')}{tip}{after}")
        if state.get("screen") == "map-screen" and len(state.get("actions") or []) > 1:
            out.append("  Picking one closes the others on this layer for good.")
        return "\n".join(out)

    # -------------------------------------------------------- 5. a kept turn's slot
    def render_scratch(self, state: dict[str, Any]) -> str:
        """In: the state of a turn being kept. Out: the one line it shows."""
        # The old screen is not sent again: it is stale, and the current one is right
        # there in the fresh message. Only what changed is worth a line.
        run = state.get("run") or {}
        team = state.get("team") or []
        low = min((p["hp"] / p["max_hp"] for p in team if p.get("max_hp")), default=1.0)
        return (f"[turn {state.get('steps')}: {state.get('screen')}, "
                f"map {run.get('map', 0)}, {run.get('badges', 0)} badges, "
                f"{len(team)} alive, weakest at {low:.0%}]")

    # -------------------------------------------------------------- 6. what is filed
    def add_metadata(self) -> dict[str, Any]:
        """In: nothing. Out: my own facts, written beside the score."""
        # Only what nothing else could know. The model, the harness generation, the
        # view and whether the tools are the stock set are already recorded.
        return {"tuned_for": "gemini-class models", "notes_policy": "one per run"}
