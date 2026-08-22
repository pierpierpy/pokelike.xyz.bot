# Harness v6, four regions

**v5 had one region. The game now has four (Kanto, Johto, Hoenn, Sinnoh), each a whole
game: a new starter, eight of its own gyms, its own Elite Four.** Clear one and the next
begins from zero. The model's notes are the only thing that crosses the boundary.

Under v5 the notes survived between runs within a single region. Under v6 they survive
between REGIONS, which is a harder test: a lesson about Brock helps in Kanto and is
useless in Johto, so the model has to figure out which notes generalise and which are
region-specific. The notebook is now the bridge between four different games, not fifty
replays of the same one.

---

**Contents**

- [What changed from v5](#what-changed-from-v5)
- [Why regions change what the benchmark measures](#why-regions-change-what-the-benchmark-measures)
- [What is frozen in here](#what-is-frozen-in-here)
- [Running it](#running-it)

---

## What changed from v5

Everything v5 does (the notebook, the plan, the three-turn scratchpad, the eight tools,
the node tooltips, the move types, the exit previews) is unchanged. v6 adds three
things:

1. **The prompt explains four regions.** The model is told that each region is a whole
   game with its own starters, eight gyms, and an Elite Four, and that notes are the only
   thing that crosses a boundary. The rest of the prompt (the memory instructions, the
   strategy advice, the tool descriptions) is kept verbatim.

2. **The region is shown in the header.** `render.py` prints `region: johto` (or hoenn,
   sinnoh) beside the step and badges when the model is not in kanto. A kanto pass
   renders byte-identically to v5.

3. **Region boundary methods.** `region_cleared(done)` returns a summary when a boundary
   is crossed; `region_opening(text)` puts that summary into the first prompt of the new
   region's journal. v5's `reset()` already clears the journal, plan and scratchpad while
   keeping the notebook, which is the right boundary behaviour; what v6 adds is the
   SUMMARY that connects one region to the next.

`HARNESS = 7`.

## Why regions change what the benchmark measures

Under v5, notes that say "Brock uses Rock, bring Water" are correct for the whole
benchmark. Under v6 they are correct for Kanto and dead weight in Johto. A model that
fills its notebook with region-specific lessons will carry useless notes into the next
region; one that writes generalisable lessons ("heal before a gym when under half HP")
will do better across four regions than across one. The benchmark now measures whether a
model can distinguish local facts from general principles, which is a different skill
from playing one region well fifty times.

## What is frozen in here

`bot.py`, `render.py`, `bridge.js`, `init.js`. **`bridge.js` and `init.js` are
byte-identical to v5**: the region field was already exposed by the shared bridge, and
the run seed is unchanged. All four are hashed into every result recorded beside this
directory and are never edited once a result exists; a new idea is v7.

## Running it

```bash
uv run pokelike model bench --harness v6 --model <provider/model> \
  --endpoint https://... --api-key sk-...
uv run pokelike model board --harness v6
```
