# Harness v1, the model keeps notes

**An experiment, not an improvement.** Every other version bump promotes something
that already earned its place in `bots/`. This one asks a question nobody here has
answered: *does a model that takes notes get better at this game while it plays?*

If the answer is no, v1 stays exactly where it is as the record of that, the same
way `experiments/dyna-q` is kept for losing. A version names what the models were
asked, never how well it went.

---

## What changed from v0

| | v0 | v1 |
|---|---|---|
| tools | `team_details`, `what_lies_ahead`, `set_lead`, `play` | those four plus `remember`, `revise`, `forget` |
| tool rounds | 4 | **6** |
| notes | none | up to **12**, of **160** characters, shown every turn |
| notes cleared | n/a | at the start of a **pass**, never between runs |
| workers | any | **1**, refused above that |

Everything else is v0 unchanged: same system prompt of facts without strategy, same
temperature 0.0, same 1500 tokens an answer, same 6-turn journal, same fallback,
same three fatal failures, same 50 fixed seeds.

### Three tools, not one

The cap is the point. Once twelve notes are held, the only way to record a better
lesson is to sharpen one or drop one, so `revise` and `forget` are what make the
cap interesting rather than merely annoying. Curating a small set of beliefs is the
skill this version tries to measure; appending to a list is not.

Every reply states how full the notebook is (`7/12 notes used`). A model that
cannot see the cap keeps calling `remember`, gets refused, and carries on as though
the lesson were saved.

Two deliberate leniencies, both to avoid spending a round on an error message: a
note longer than 160 characters is **truncated, not rejected**, and an id that does
not exist is **answered** ("there is no note [9], you have 3") rather than raised.

There is no tool to *read* the notes, because they are already in the prompt:

```
WHAT YOU HAVE LEARNED (kept across runs, 3/12):
  [1] Trainer nodes are safe with a lead two levels above the map.
  [2] Never enter a wild battle below half HP; heal first.
  [3] Taking the item node on layer 2 costs the only heal.
```

Numbered from 1, because those numbers are the ids `revise` and `forget` take, and
an off-by-one between what the model is shown and what the tool accepts would look
to the model like a broken tool.

They sit **above** the journal, on the grounds that what was learned across fifty
runs outranks what happened in the last six turns of this one.

### Why six rounds

Memory operations consume rounds, and a turn that runs out of rounds is played by
the fallback heuristic under the model's name. At four rounds a model would be
penalised for doing exactly what this version asks of it.

### Why the notes are cleared per pass

A pass builds one bot and plays all fifty seeds with it. The notes survive
`on_start`, so they cross from run to run; nothing survives the bot, so the next
pass starts naive. That is the whole feature, and it is arranged this way rather
than with a reset call because there is then nothing to forget to call.

Passes stay comparable to each other. Notes persisting across passes would make
pass 2 a continuation of pass 1, and the repeat spread would stop being a measure
of variance.

## What this costs: the runs are no longer independent

Run 3 depends on what the model wrote during runs 1 and 2. Three consequences, all
of them enforced or reported rather than papered over:

- **No parallelism.** `--workers > 1` is refused, in the CLI before the pre-flight
  spends a token and again inside `fan_out` where it cannot be bypassed. Eight
  workers would mean eight separate notebooks, each covering a fraction of the pass,
  and a result that depends on how the seeds were dealt out, in a row that would
  look completely ordinary. A pass is about half an hour, and that is the price.
- **Seed order is part of the harness**, not an implementation detail. Every run
  records `order`, which run of the pass it was; rows are stored sorted by seed, and
  a memory harness is only interpretable in the order it was played.
- **The fifty numbers are a learning curve**, not fifty draws from one distribution.
  `badges~` is still printed, because it is what compares to v0, but a mean over a
  learning curve averages a naive model with a practised one. The column this
  version exists to produce is `learn`: the last ten runs of a pass minus its first
  ten, computed per pass and then averaged, never pooled across passes, because pooling
  would compare one lifetime's start against another lifetime's end.

## What a result carries

Every run row keeps the notebook **as it stood when that run ended**, not one
snapshot at the end of the pass. A single final snapshot cannot show a lesson being
learned and then revised away, which is the most interesting thing that can happen
here.

```json
{ "seed": 10007, "order": 8, "badges": 2,
  "notes_kept": 3,
  "notebook": ["Trainer nodes are safe with a lead two levels above the map.", "..."] }
```

The log is tail-able while it runs: a `notes` column, a `+`/`-` line every time the
notebook changes, and the final notebook printed when the pass ends.

```
  seed  badges  steps        in       out  fell  retry     secs  notes
 10000       1    214     28431      1502     0      0     41.2      2
       + Trainer nodes are safe with a lead two levels above the map.
```

## Cost, against v0

Notes go into every prompt of every turn, so v1 spends more input tokens for the
same fifty runs. A full notebook is roughly 500 tokens; at about twenty turns a run
that is a few hundred thousand extra input tokens a pass, on the order of a third
more than v0. This is also why the cap exists: uncapped notes would grow without
limit and the comparison would stop being about memory.

## What is frozen, and what is not

Identical to v0, and read [that README](../../v0/harness/README.md) for the full
argument. In short: four files here are frozen and must not be edited once a result
exists under `../results/`, namely `bot.py` (a mechanical copy generated from v0
rather than transcribed), `render.py`, `bridge.js` and `init.js`. `browser.py`,
`game.py` and `runner.py` stay shared and are hashed into every result instead.

The header inside `bot.py` still describes the renderer as imported from
`pokelike.core`; it cannot be corrected without invalidating the rows beside it.

One naming trap worth knowing if you read the file: `self.memory` is **not** the
notes. It is v0's journal-trim size (`MEMORY = 6`), and `_commit` slices the journal
with it. The notes are `self.notebook`.

## Running it

```bash
export FW_ENDPOINT="https://openrouter.ai/api"
export FW_TOKEN="..."
uv run pokelike model bench --harness v1 --model <the model id> --repeat 1

# or with no exports at all
uv run pokelike model bench --harness v1 --model <the model id> --repeat 1 \
  --endpoint https://openrouter.ai/api --api-key @~/.openrouter-key
```

No `--workers`. It will not come out identical twice, for the same reasons v0 does
not, because providers change models behind a fixed name and sampling is stochastic, and now
also because a different early note leads to a different later run. Every result
says `reproducible: false`.

The comparison the version is for costs two passes of the same model:

```bash
uv run pokelike model bench --harness v0 --model <id> --workers 4
uv run pokelike model bench --harness v1 --model <id>
```
