# Harness v3, the same loop with better eyes

**The benchmark was measuring how well models play half blind.** The game puts text
under the pointer on every map node: the trainer's archetype and which types they
use, a gym leader's roster with levels, what a trade does. Under `v0`, `v1` and `v2`
none of it was in the state at all. A model chose between `battle` and `trainer`
knowing the words `battle` and `trainer`, and nothing else.

That is a defect in the instrument, not a difficulty setting. A person playing in a
browser reads it before choosing.

---

**Contents**

- [What changed from v2](#what-changed-from-v2)
- [The tooltips](#the-tooltips)
- [The move tutor block](#the-move-tutor-block)
- [The journal](#the-journal)
- [What did not change](#what-did-not-change)
- [What a v3 row means](#what-a-v3-row-means)
- [What to expect](#what-to-expect)
- [What is frozen in here](#what-is-frozen-in-here)

---

## What changed from v2

| | `v2` | `v3` |
|---|---|---|
| node tooltips | not in the state | read from the engine, shown on every option |
| MOVE TUTOR block | printed every turn | only on the tutor screen |
| journal line | the model's own sentence | the action taken, with the sentence labelled under it |
| agent loop | scratchpad, plan, notes, 8 tools | identical |
| prompt | explains the loop and how to play | identical |

Three changes, and none of them touches the loop. That is deliberate: `v2` changed
five things at once and said so, and the gain could not be attributed. This one moves
what the model is looking at and leaves everything else where it was.

## The tooltips

What the game actually says, now in the state and on every legal option:

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

Knowing Brock leads Geodude and Onix, both Rock, is the difference between arriving
with a Water starter and arriving with whatever survived.

Read by calling the engine's own `getNodeLabel(node)`, the function that builds the
tooltip's HTML, so it cannot drift from what is displayed. **Not** by synthesising
mouse events over each node: that injects events into a game we do not control, and
the settle loop exists because pumping the engine makes it consume its seeded RNG in
a different order, at which point the same seed stops replaying the same run.

Unrevealed nodes are skipped. Every node in Story mode has come back revealed so far,
so that guard has never fired; it is there because the day it stops being true, the
failure would be a bot quietly reading a face-down card.

## The move tutor block

Under `v0` to `v2` this was printed on **every** turn, because the bridge fills
`offered_moves` unconditionally and nothing gated on the screen. Measured on seed
10000: it was on 11 of the first 13 turns, and not one of them was a tutor.

187 characters a turn, on the order of 58k tokens across a fifty-run pass, describing
an exchange that was not on offer. A model that reasoned about it was reasoning about
nothing; one that ignored it paid for the tokens anyway.

## The journal

`v0` to `v2` recorded the model's own sentence and showed it back under a heading
reading `YOUR RECENT MOVES`. So a plan came back as a record of events one turn later,
with nothing to tell the two apart.

Now the action comes from the harness's own data and the sentence sits underneath,
labelled:

```
WHAT YOU DID, AND WHAT YOU SAID AT THE TIME.
  step 7: [0] node n2_1 (trainer), Firebreather — +2 Levels — Fire Pokemon
    it said: a second Pokemon matters more than one more fight this early
```

This matters more here than it would have under `v0`, because `v2` added a scratchpad:
the model already sees its own words from the last three turns verbatim. There were
two channels carrying its reasoning and one of them was labelled as fact.

## What did not change

The prompt, the eight tools, the scratchpad of three turns, twelve notes across runs,
six tool rounds, 4000 tokens an answer, temperature 0. Everything `v2` said about why
those are what they are still stands, and is not repeated here.

## What a v3 row means

> How well does this model play when told the rules and how to use the loop, seeing
> what a person sees.

`v0` asked how well it plays told only the rules. `v2` asked the same as `v3` minus
the eyes. Three questions, three tables. Comparing across them mixes the change with
the answer, which is why the version is in the path.

## What to expect

Written down first so it cannot be adjusted afterwards.

**Badges up, input per run roughly flat.** The tooltips add a few hundred characters a
turn and the tutor block removes about as many. Expect it to help the careful models
most: under `v0` the ranking followed input per run, which is to say it followed how
much a model had bothered to look at, and looking is now worth more.

**If badges do not move, that is the more interesting result.** It would say the models
were not losing for want of information, and that the ceiling is somewhere else.

## Models served by OpenAI cannot be measured here

v3 inherits v2's agent loop, and with it the defect
[described there](../../v2/harness/README.md#models-served-by-openai-cannot-be-measured-here):
the exchange that ends a turn is stored with the `play` call in it and no reply to
that call, so from the second turn every request carries an assistant message with
an unanswered `tool_call_id`. OpenAI's API refuses the whole request.
`openai/gpt-4o-mini` fell back on 12 turns out of 13, each one an HTTP 400.

Providers that do not check the pairing accept it. It is fixed in
[v4](../../v4/harness/README.md), which is a new directory precisely because this
one cannot be edited once a row exists under `../results/`.

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
which drive the game. Freezing those too would mean each harness carrying its own
browser plumbing. Every result records a sha256 of all seven, plus the name and hash
of the game bundle, and the table marks a row when any of them stops matching disk.

**Do not edit any of these once a result exists under `../results/`.** The next idea
is `llm-bench/v4/harness/`, a fresh directory.
