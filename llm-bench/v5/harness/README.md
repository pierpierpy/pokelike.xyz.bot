# Harness v5, the model can see what it is fighting with

The v4 harness told the model what it was fighting against (node tooltips: "Brock: Rock
Gym | Onix Lv14") but never what it was fighting with. The team view showed a move's name
and power, not the move's type, so the one fact that decides a battle ("does my move's
type beat theirs") was missing from the screen. v5 puts that fact back.

LLMs already know the type chart from pretraining. The gap was never knowledge; the gap
was that the state hid the inputs. Showing move types is the lever prior work
([PokéLLMon](https://arxiv.org/abs/2402.01118)) measured as the single biggest one.

---

Contents

- [What changed from v4](#what-changed-from-v4)
- [Why not dump the type chart](#why-not-dump-the-type-chart)
- [What is frozen in here](#what-is-frozen-in-here)
- [Running it](#running-it)

---

## What changed from v4

Everything v4 does (the notebook, the plan, the three-turn scratchpad, the eight tools,
the node tooltips) is unchanged. v5 adds three things, all in `render.py`, plus one line
of prompt in `bot.py`:

1. Move type, physical/special, and STAB now appear in the team view. Each Pokemon now
   reads `Squirtle Lv7 24/24 Water  Water Gun 40 Water(sp) STAB` instead of stopping at
   the power. The type and the STAB flag are the inputs a type-matchup decision needs.

2. Exit previews now appear on the map. Each legal node now shows where it leads on the
   next layer (`-> next: trainer, item`), read from the graph's edges. The connectivity
   that only the `what_lies_ahead` tool gave before is now in front of the model every
   turn. That visibility matters because a node closes the others on its layer when
   picked, so what a node opens up is what makes it worth taking.

3. Move types now appear at the tutor. The `tutor_view` function shows the type and
   physical/special of both the current and offered move, and STAB, so a tutor choice is
   type-aware too.

The prompt gains one short static `TYPE MATCHUPS` block explaining super-effective,
resist, dual-type multiplication and STAB, and to line the lead's move type up against
the tooltip before a fight.

The version constant in the code is `HARNESS = 6`.

## Why not dump the type chart

The 18×18 type chart and the full move pool are deliberately not put in the prompt.
Adding hundreds of irrelevant entries every turn is the "context rot" pattern that
measurably lowers decision quality, and this repo's own `llm-raw` bot already showed
that a bigger dump is not a better one. The model knows type effectiveness from
pretraining; v5 gives the model the two facts it could not see (its own move's type and
where each path leads) and nothing else.

## What is frozen in here

The files frozen here are `bot.py`, `render.py`, `bridge.js`, and `init.js`. The
`bridge.js` and `init.js` files are byte-identical to v4: v5 needs no new data from the
engine, only a fuller rendering of what the state already carries (`team[i].move.type`,
`types`, and the map `edges`). All four are hashed into every result recorded beside this
directory and are never edited once a result exists; a new idea belongs in v6.

## Running it

```bash
uv run pokelike model bench --harness v5 --model <provider/model> \
  --endpoint https://... --api-key sk-...
uv run pokelike model board --harness v5
```
