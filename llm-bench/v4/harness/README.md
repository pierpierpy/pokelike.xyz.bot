# Harness v4, memory the model is told to run

**Two of the four models measured under v2 called `remember` zero times in fifty runs.**
The notebook was there, the tools were callable on any turn, and v2's prompt said to
write "a lesson you want to have in the NEXT run, not a reminder for later this turn",
which is an instruction not to use it while playing. There is no end of a run to write
at either: a run stops the moment the team is wiped out.

So the silent prompt could only ever produce one of two findings. "Memory does not help"
and "the models never touched the memory" are different results, and v0 to v3 could not
tell them apart. This one can.

---

**Contents**

- [What changed from v2](#what-changed-from-v2)
- [The memory, and what it costs to ask for it](#the-memory-and-what-it-costs-to-ask-for-it)
- [The cap as a setting](#the-cap-as-a-setting)
- [Every tool call, in order](#every-tool-call-in-order)
- [What came from v3](#what-came-from-v3)
- [The play call is answered](#the-play-call-is-answered)
- [What a v4 row means](#what-a-v4-row-means)
- [What to expect](#what-to-expect)
- [What is frozen in here](#what-is-frozen-in-here)
- [Running it](#running-it)

---

## What changed from v2

| | `v2` | `v4` |
|---|---|---|
| the notebook | allowed, and framed as an end-of-run lesson | **asked for**: at least one note a run, with examples |
| the plan | mentioned once in the advice | **asked for** on every map, with examples of both kinds |
| the cap | 12, in the code and as a word in the prompt | 12 by default, `--set notes=N`, in the prompt as a number |
| node tooltips | not in the state | read from the engine, on every option |
| MOVE TUTOR block | printed every turn | only on the tutor screen |
| journal line | the model's own sentence | the action taken, with the sentence labelled under it |
| what the trace holds | the choice and the sentence | that, plus every tool call in order |
| the `play` call | stored with no reply to it | answered, so any provider accepts the history |
| loop and tools | scratchpad of 3, plan, 8 tools, 6 rounds | identical |

## The memory, and what it costs to ask for it

The prompt now says the notebook is part of playing, asks for **at least one note per
run**, and shows what a note is for:

```
NOTES THAT ARE WORTH THE SPACE. Each is a rule for the next run, and each carries a
number or a name:
  "map 0 trainers are safe with a level 8 lead; map 1 trainers carry 2 Pokemon"
  "skipping the pokecenter before the gym lost me 3 runs at exactly 1 badge"
  "Brock leads Geodude Lv12 and Onix Lv14, both Rock: a Water lead walks it"

NOTES THAT WASTE IT:
  "I am on map 1"            -- false in a minute
  "be careful with trainers" -- no number, so no decision changes
  "I chose the trainer node" -- the journal already tells you that
```

It also says when to write: when a fight goes worse than expected, when the team is
nearly gone and there is still a turn left, when something believed turns out wrong. And
that a full notebook is a reason to `forget` the weakest note, not a reason to stop.

**What that costs, said plainly.** A prompt that tells a model to call a tool measures
how well it follows that instruction as much as how well it plays. That is a real loss
and it is taken deliberately, because the alternative was a column that could not
distinguish a model with nothing worth writing from a model that never tried.

The plan is asked for on the same terms, with the same treatment:

```
A plan that helps: "n1_0 catch for a second body, n2_1 trainer for levels,
skip the item at n3_2, pokecenter n7_0 before the gym"
A plan that does nothing: "level up and beat the gym"
```

## The cap as a setting

`NOTES_MAX = 12` is the declared default, and `--set notes=N` changes it per pass. The
prompt carries the real number rather than the word "twelve", so what the model is told
and what the tool enforces cannot drift apart.

`--set` is how a harness takes a setting no other version understands: it goes straight
to the constructor, which refuses by name what it does not know. There is nothing to add
to the CLI when a later version invents a knob of its own.

```bash
uv run pokelike model bench --harness v4 --model qwen/qwen3.7-flash --set notes=4
```

Every run row records `notes_max`. **A pass with a different cap is a different
question**, so a row measured at 5 and a row measured at 12 are not each other's
competition, any more than a v2 row is a v4 row.

## Every tool call, in order

Each decision in the pass trace carries the calls that produced it:

```json
{"at": "2026-08-20T17:41:02", "seed": 10000, "step": 7, "chose": 0,
 "tools": [{"tool": "what_lies_ahead"},
           {"tool": "remember", "note": "map 0 trainers are safe at level 8", "kept": 3},
           {"tool": "play", "index": 0, "why": "keeps two paths open"}]}
```

Read-only tools appear as a name: what they answered is rebuildable from the state,
which is already in the trace. The ones that change something carry what they changed,
refusals included: `{"tool": "remember", "refused": "notes full", "kept": 12}`.

**A refusal that is not recorded reads afterwards as a model that never tried.** Before
this, that is exactly what `remember` against a full notebook looked like: nothing at
all.

This is also the only way to answer what a model does with the eight tools it is given.
Measured on the first three v4 passes, over 147 decisions: `what_lies_ahead` on about
half the turns, `team_details` between one and five times each, and `set_lead` seventeen
times for one model and never for another.

**Every harness records this now, not only v4.** It started here, and v0 and v2 were
given the same recorder afterwards: a list appended to in the dispatch loop leaves the
request, the reply and every branch untouched, so it is an observation and belongs to
all of them. Their eleven recorded passes carry the old hashes and the reason beside the
new ones. It lives in each harness rather than in the shared code because the loop is
the harness: `play` and `set_lead` never reach `run_tool`, so nothing outside can see
the decision itself.

`pokelike model watch` reads this while the pass runs.

## What came from v3

v3 was deleted, unmeasured, and its three changes are here. They are about what the
model can see, and each one was a defect in the instrument rather than a difficulty
setting.

**The node tooltips.** The game puts text under the pointer on every map node: the
trainer's archetype and which types they use, a gym leader's roster with levels, what a
trade does.

```
ACTIONS
  [0] go to node n1_0   (catch)  Catch Pokemon
  [1] go to node n1_1   (battle)  Wild Battle — +1 level
```

and the ones that carry a real decision:

```
  Officer — +2 Levels — Fire Pokemon
  Brock — Rock Gym | Geodude Lv12 | Onix Lv14
  Trade — swap a Pokémon for one 3 levels higher
```

Under v0 to v2 none of it was in the state at all. Read by calling the engine's own
`getNodeLabel(node)`, so it cannot drift from what is displayed, and **not** by
synthesising mouse events: pumping the engine makes it consume its seeded RNG in a
different order, at which point the same seed stops replaying the same run. Unrevealed
nodes are skipped.

**The MOVE TUTOR block, only at the tutor.** Under v0 to v2 it was printed every turn,
because the bridge fills `offered_moves` unconditionally and nothing gated on the screen.
On seed 10000 it was on 11 of the first 13 turns, not one of them a tutor: 187 characters
a turn describing an exchange that was not on offer.

**The journal separates what was done from what was said.** v0 to v2 recorded the
model's own sentence under a heading reading `YOUR RECENT MOVES`, so a plan came back as
a record of events one turn later with nothing to tell the two apart.

```
WHAT YOU DID, AND WHAT YOU SAID AT THE TIME.
  step 7: [0] node n2_1 (trainer), Firebreather — +2 Levels — Fire Pokemon
    it said: a second Pokemon matters more than one more fight this early
```

## The play call is answered

v2 stored the exchange that ended the turn with the `play` call in it and no reply to
that call, because the turn returns the moment it is seen. From the second turn on,
every request carried an assistant message with an unanswered `tool_call_id`.

OpenAI's API refuses the whole request for it:

> An assistant message with 'tool_calls' must be followed by tool messages responding
> to each 'tool_call_id'.

Providers that do not check the pairing accept it, which is why it survived: every model
measured under v2 was served by one of them. **No model served by OpenAI could be
measured under v2 at all**: `openai/gpt-4o-mini` fell back on 12 of 13 turns, each one an
HTTP 400. Here every call in the exchange is answered before it is stored, `play`
included, and the same model finished a run with fallback 0.0.

## What a v4 row means

> How well does this model play when it sees what a person sees, is told how to use the
> loop, and is told to run its own memory while it plays.

## What to expect

Written down first so it cannot be adjusted afterwards.

**Notes written in most runs**, where v2 had two models out of four writing none at all.
That is the change being made, so it is the least interesting prediction here.

**`learn` not much larger.** Being told to write does not make what is written worth
reading. If `learn` does move, the number to read is not the badges: it is how many
operations a run it took to get there, which the trace now carries.

## What is frozen in here

Four files, and nothing outside this directory can reach them:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

`bridge.js` is frozen for a stronger reason than the renderer: a bot answers with an
**index** into `actions`, so reordering that list does not change what the model sees,
it changes what its answer means. `init.js` is stronger again, since the run seed is
built from `Date.now()` and `Math.random()`: moving a constant there does not mark a
recorded score, it voids it, because every seed would map to a different run.

Still shared, and hashed rather than copied: `browser.py`, `game.py` and `runner.py`,
which drive the game. Every result records a sha256 of all seven, plus the name and hash
of the game bundle, and the table marks a row when any of them stops matching disk.

**Do not edit any of these once a result exists under `../results/`.** The next idea is
`llm-bench/v5/harness/`, a fresh directory. The counterpart of that rule is what
happened to v1 and v3: a version with no recorded row is keeping nothing, so they were
deleted rather than left as directories nobody could compare against.

## Running it

```bash
uv run pokelike model bench --harness v4 --model <id> \
  --endpoint https://openrouter.ai/api --api-key @~/.key
```

No `--workers`: the notebook crosses runs, so the runs are not independent and more
than one worker is refused.
