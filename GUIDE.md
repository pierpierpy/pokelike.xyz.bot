# Entering the contest

Six steps from a clone to a pull request. None of them is optional. The one that
is easy to get wrong is marked, and the rule that catches people out has
[a section of its own](#the-rule-that-is-not-obvious).

---

**The six steps**
- [1 Set up](#1-set-up-once) 
- [2 See the state](#2-look-at-what-a-bot-receives) 
- [3 Create it](#3-create-it) 
- [4 Write it](#4-write-it) 
- [5 Measure it](#5-measure-it) 
- [6 Submit](#6-submit)

**Then**
- [The optional hooks](#the-optional-hooks) 
- [The rule that is not obvious](#the-rule-that-is-not-obvious) 
- [Two people, one name](#two-people-one-name) 
- [Where to experiment](#where-to-experiment) 
- [Pushing your experiments too](#pushing-your-experiments-too) 
- [What counts as a bot](#what-counts-as-a-bot)

---

## 1. Set up, once

Fork this repo on GitHub first, then clone **your** fork, not this one. That way
`origin` is somewhere you can push, which is what step 6 needs:

```bash
git clone https://github.com/YOUR-HANDLE/pokelike.xyz.bot && cd pokelike.xyz.bot
uv sync
uv run pokelike setup          # the browser plus an offline copy of the game, ~130 MB
```

The copy is offline on purpose: after this nothing you do reaches the internet,
and the same seed always replays the same run.

## 2. Look at what a bot receives

Do not guess at it. This is generated from a live observation, so it cannot
describe a game that no longer exists:

```bash
uv run pokelike schema         # the full reference
uv run pokelike play           # play it yourself; three minutes is enough
```

Two things decide how you write everything else.

The state is **one dict, not a history**. What history matters is already inside
it: every map node carries `visited`, and `stats` are cumulative from the start
of the run.

**The indices change every turn.** `state["actions"]` is the list you choose
from, and index 2 is a battle now and a catch next turn. Nothing can be decided
by position; you look at what each entry actually is.

It is worth watching a trained bot play before you write
anything. Pick whichever is leading from [the standings](bots/README.md):

```bash
uv run pokelike bot --bot sarsa-v2 --seed 40003 --runs 1 -g -dd
```

`-g` draws the map beside each decision, `-dd` prints the value it gave every
option before choosing.

## 3. Create it

```bash
uv run pokelike new-bot mine
```

That writes a folder, and the folder **is** the bot:

```
bots/mine/
├── bot.py        one class inheriting from Bot
├── artifacts/    weights, prompts, tables, whatever yours needs
└── README.md     one line on how it decides
```

Nothing to register anywhere. `--bot mine` finds it because the folder is there.
A prefix works too as long as it is unique, so `--bot mi` is fine until someone
adds `mine-v2`, at which point it becomes an error naming both rather than a
guess.

**If your bot is a prompt around a language model**, add `--llm` and you start
from the shared harness instead of an empty `choose`:

```bash
uv run pokelike new-bot my-prompt --llm
```

You then write nothing but the prompt. The tools, the agentic loop, the state
rendering, the HTTP call and what happens when it fails all live in
`pokelike.bot.llm` and are shared by every LLM bot **on purpose**: two bots with
different loops are two harnesses being compared, and the model is the smaller
half of that difference.

If the prompt is not where your idea lives, you can go further without leaving
the harness. `STATE_VIEW` decides what the model reads each turn, the rendered
view by default, or `"json"` for the whole state dict, or a list of the keys you
want; `view(state)` is there when none of those fit. `EXTRA_TOOLS` and
`run_tool` give the model something the shared tools do not offer, and
overriding `_call` puts a different model behind it.
a local one, or anything that is not an HTTP endpoint at all. Both are recorded
in your result, so your row says what it actually was.

What it writes already plays, which matters more than it sounds: measure it
before you change a line, and when the number moves later you know it moved
because of you.

```bash
uv run pokelike bot --bot mine --runs 5 -d
uv run pokelike bench --bot mine --dry-run     # the real 50 seeds, recorded nowhere
```

## 4. Write it

The only method you must write is `choose`. It gets the state and returns an
index into `state["actions"]`.

```python
from typing import Any

from pokelike.bot.base import Bot


class MyBot(Bot):
    name = "mine"

    def choose(self, state: dict[str, Any]) -> int:
        """Heal when someone is hurt, otherwise take a trainer for the levels."""
        team = state.get("team") or []
        hurt = any(p["hp"] / p["max_hp"] < 0.5 for p in team if p["max_hp"])

        for i, a in enumerate(state["actions"]):
            if hurt and a.get("node") == "pokecenter":
                return i
        for i, a in enumerate(state["actions"]):
            if a.get("node") == "trainer":
                return i
        return 0
```

Everything the game knows is in `state`, including things nothing on screen tells
you: `team[i].move` is what that Pokemon actually attacks with, power and type
included, and `offered_moves` is what the move tutor would hand each of them.

**One class per folder.** The name of the folder says which bot ran, so a file
defining two of them is refused rather than guessed at.

## 5. Measure it

One measurement, the official benchmark: the 50 fixed seeds everyone is scored
on. There is deliberately no second protocol, because runs vary enormously by luck, so
a hand-picked seed set mostly measures who drew the nicer maps, and the same
weights can score 1.60 on one set and 1.10 on the official 50.

```bash
uv run pokelike bench --bot mine --dry-run                       # nothing recorded
uv run pokelike bench --bot mine --author YOUR-HANDLE --category rules
```

If yours calls a model, the credentials can come from flags instead of exports.
`--api-key @path` reads a file, so the key never reaches your shell history:

```bash
uv run pokelike bench --bot mine --dry-run \
  --endpoint https://openrouter.ai/api --api-key @~/.key --model openai/gpt-4o-mini
```

> **Easy to get wrong, and now it cannot be.** Only a **complete** run records a
> result. `--runs N` is a practice run by definition, since a score over 5 seeds is
> not comparable to one over 50, and `--dry-run` plays all 50 and records
> nothing. Neither leaves anything behind for a stray `git add` to pick up.

A recorded result lands in `bots/mine/result.json`, next to the code that earned
it, with a fingerprint over both. If you then edit the bot, the table marks the
row **⚠︎** until you measure it again: a score can never quietly describe code
that no longer exists.

## 6. Submit

You forked in step 1, so `origin` is your fork and there is nothing left to set
up:

```bash
git checkout -b my-bot
git add bots/mine
git commit -m "Add my-bot"
git push origin my-bot
```

Then open the pull request GitHub offers you, from your fork to this repo. Your
whole submission is one folder.

### One folder, and why that is the whole of it

A pull request that touches only `bots/` is read as a submission and usually merged
as is. One that also changes `src/` or `llm-bench/` gets a slower read, because those
two directories are what makes every recorded score comparable, and a change there is
usually landed by hand rather than merged.

That is not a fence against your ideas, it is a fence around the numbers. Almost
everything people reach into the library for can be done from inside your folder:
`PROMPT`, `STATE_VIEW`, `view()`, `EXTRA_TOOLS`, `run_tool()`, `_call()`. The one
thing that cannot is adding data the bridge never read from the game.

And if what you found is a **bug** in the shared code, that is wanted, not tolerated.
Two of the worst defects found so far came from someone building a bot on a fork and
noticing the library was lying to their model. Open an issue. See
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## The optional hooks

Only `choose` is required. These exist for bots that need them, and ignoring one
costs you nothing:

| hook | what it is for |
|---|---|
| `rearrange(state)` | who leads the next battle. Free, it does not use the turn |
| `explain()` | one line under each decision in the log |
| `on_start(seed)` / `on_end(state, score)` | a bot with memory across turns |
| `artifacts()` | weights and config to record beside your result |

`rearrange` is worth a look. Slot 0 is the Pokemon that enters the next battle,
so the order is a real decision, and it is kept out of `actions` because taking
it costs no turn: a full team would otherwise add fifteen swap pairs beside the
real moves at every single map node.

---

## The rule that is not obvious

> **Your folder has to stand on its own.** Everything `bot.py` needs is either in
> the `pokelike` package or in `artifacts/` beside it. It must not import from
> `experiments/`, and it must not import another bot.

Two reasons, and the second is the one people underestimate.

A trained policy is only meaningful under the exact encoding it was trained with.
If `bot.py` imported its feature code from your training scripts, improving those
scripts would silently change what your own past score meant, and the
fingerprint would not catch it, because the file you measured did not change.

And a bot is meant to be handed around, re-run and checked by someone who has
none of your setup. A folder that only works on the machine that made it is not
a submission, it is a screenshot.

[`bots/dyna-q/`](bots/dyna-q/) is the small worked example, with an encoding frozen
beside its weights. [`bots/sarsa-v2/`](bots/sarsa-v2/) is the large one, 100
feature definitions carried inline for exactly this reason.

**The one exception is `pokelike.bot.llm`**, the harness the `llm-*` bots share.
It is shared knowingly, so editing it *does* reach every LLM bot ever measured,
which is why it carries a `HARNESS` number that is written into every result, and
why a row measured under an older one is flagged instead of being ranked as
though it had been asked the same question.

### Two people, one name

`bots/` is flat, so two submissions cannot share a folder name. Git will say so
on your pull request and one of you renames. A plain conflict, visible, nothing
auto-resolved. The `--author` you pass to `bench` is what tells people apart in
the standings. The fingerprint is not a name and is deliberately not used as one:
it comes from the content, so it would change every time you retrained.

---

## Where to experiment

`experiments/` is a scratch area and **nothing you add there is tracked by
default**: everything under it is gitignored apart from the shared `env/` and our
own worked examples. Whatever you try, from training runs and sweeps to prompts and dead
ends, stays on your machine unless you say otherwise, and a pull request that adds a
bot cannot drag a training run along with it by accident.

```bash
cp -r experiments/example experiments/mine
uv run python -m experiments.example.train --episodes 20   # the shape of one
```

And you measure a candidate right where it lives. Write a `bot.py` in your
experiment folder and point the benchmark at it:

```bash
uv run pokelike bench --bot experiments/mine --dry-run
```

Measured by path, never recorded. When it earns its place, bring it into
`bots/` the standard way (step 3) and bench it there, under its own name.

That is the split, and it is the whole answer to "what do I have to reveal":

**You show what your bot does. Not how you arrived at it.**

Submitting a folder does reveal the bot, and that is the only reason the number
beside it means anything, since a leaderboard where the code is hidden is a list
of claims. It reveals nothing about the sweeps, the rewards you tried, or the
twenty runs that went nowhere.

## Pushing your experiments too

That default is a **default, not a rule**. The research is yours, which means it
is yours to publish as much as it is yours to keep. Ours are checked in for
exactly that reason, because they are meant to be read, and if you want the same for
yours, it is one line.

Add a negation for your folder in `.gitignore`, next to the ones already there:

```
experiments/*
!experiments/env/
...
!experiments/mine/          # <- yours
```

Then `git add experiments/mine` picks up the code and nothing else, because the
three rules below that block still apply to every experiment including yours:

```
experiments/*/output/       weights, data shards, histories
experiments/*/logs/         what each run printed
experiments/*/artifacts/    the weights a candidate bot.py reads
```

So a whitelisted experiment commits its **code and its README** (the loop, the
features, the reasoning, the results you wrote down) and never the hundreds of
megabytes a run produced. That split is deliberate: `artifacts/` is in the ignored
list because an experiment's `bot.py` is a *candidate*, and its weights only
become something to commit when the bot earns a folder under `bots/` and is
measured there under its own name.

Check it did what you meant before committing, rather than after:

```bash
git status --short experiments/mine
git check-ignore -v experiments/mine/output/whatever.json   # should print the rule that caught it
```

Two things worth knowing if you put an experiment in a pull request. It is a
larger thing to ask of a reviewer than a bot is. A bot is one folder with one
method and a score, an experiment is a claim about *why* something works, so say
in the description what question it asks and what the answer turned out to be,
the way [`experiments/`](experiments/) does. And it is entirely separable: a pull
request that adds only `bots/mine/` is complete on its own, and nobody will ask
you for the training code behind it.

---

## What counts as a bot

Anything that picks a move given the state. A prompt around an LLM, a model
fine-tuned on the game, reinforcement learning of any flavour, a hand-written
rulebook, search over the game tree since the engine ships a battle simulator you
can call, something deterministic if you can find one that works.

Ranked by **badges**, the game's own progress counter. The bar and the current
standings are in [bots/README.md](bots/README.md).
