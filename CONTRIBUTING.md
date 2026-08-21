# Contributing

Two parts, and most people only need the first. **Part 1** is writing and submitting a
bot, six steps from a clone to a pull request. **Part 2** is changing the repo itself: a
bug, the shared library, or a new benchmark harness. A bot needs nothing from Part 2: one
folder in `bots/`, one pull request, and inside that folder the rules are yours.

---

**Contents**

- [Part 1: Write and submit a bot](#part-1-write-and-submit-a-bot)
  - [What counts as a bot](#what-counts-as-a-bot)
  - [Where to experiment](#where-to-experiment)
  - The six steps: [1 Set up](#1-set-up-once) · [2 See the state](#2-look-at-what-a-bot-receives) · [3 Create it](#3-create-it) · [4 Write it](#4-write-it) · [5 Measure it](#5-measure-it) · [6 Submit](#6-submit)
- [Part 2: Changing the repo itself](#part-2-changing-the-repo-itself)
  - [Found a bug](#found-a-bug)
  - [What lands how](#what-lands-how)
  - [Why `llm-bench/` is closed](#why-llm-bench-is-closed)
  - [The one file to be careful with](#the-one-file-to-be-careful-with)
  - [Proposing a new harness](#proposing-a-new-harness)
  - [Running the tests](#running-the-tests)

---

# Part 1: Write and submit a bot

Two things first, what qualifies, and where to try things out, then six steps from a
clone to a pull request. Everything beyond the minimum, the optional hooks, the LLM
harness knobs and seams, and shipping your own `bridge.js`, is documented in the classes
you inherit from, `pokelike.bot.base.Bot` and `pokelike.bot.llm.LLMBot`.

## What counts as a bot

Anything that picks a move given the state. A prompt around an LLM, a model fine-tuned
on the game, reinforcement learning of any flavour, a hand-written rulebook, search over
the game tree since the engine ships a battle simulator you can call, something
deterministic if you can find one that works. If it turns a state into an index, it
qualifies. Entries are ranked by **badges**, the game's own progress counter, and the
standings are in [bots/README.md](bots/README.md).

## Where to experiment

`experiments/` is a scratch area, and **nothing you add there is tracked by default**,
so a pull request that adds a bot cannot drag a training run along with it. Copy the
closest example, work there, and measure the candidate right where it lives:

```bash
cp -r experiments/example experiments/mine
uv run python -m experiments.example.train --episodes 20
uv run pokelike bot bench --bot experiments/mine --dry-run   # by path, records nothing
```

When it earns its place, bring it into `bots/` the standard way (step 3) and bench it
there under its own name. The research area is walked through in
[experiments/README.md](experiments/README.md). That is the whole answer to "what do I
have to reveal": **you show what your bot does, not how you arrived at it.**

## 1. Set up, once

Fork this repo on GitHub first, then clone **your** fork, not this one. That way
`origin` is somewhere you can push, which is what step 6 needs:

```bash
git clone https://github.com/YOUR-HANDLE/pokelike.xyz.bot && cd pokelike.xyz.bot
uv sync
uv run pokelike setup          # the browser plus an offline copy of the game, ~130 MB
```

The copy is offline on purpose: after this nothing you do reaches the internet, and the
same seed always replays the same run.

## 2. Look at what a bot receives

Do not guess at it. This is generated from a live observation, so it cannot describe a
game that no longer exists:

```bash
uv run pokelike schema         # the full reference
uv run pokelike play           # play it yourself; three minutes is enough
```

Two things decide how you write everything else.

The state is **one dict, not a history**. What history matters is already inside it:
every map node carries `visited`, and `stats` are cumulative from the start of the run.

**The indices change every turn.** `state["actions"]` is the list you choose from, and
index 2 is a battle now and a catch next turn. Nothing can be decided by position; you
look at what each entry actually is.

It is worth watching a trained bot play before you write anything. Pick whichever is
leading from [the standings](bots/README.md):

```bash
uv run pokelike bot run --bot sarsa-v2 --seed 40003 --runs 1 -g -dd
```

`-g` draws the map beside each decision, `-dd` prints the value it gave every option
before choosing.

## 3. Create it

```bash
uv run pokelike bot new mine
```

That writes a folder, and the folder **is** the bot:

```
bots/mine/
├── bot.py        one class inheriting from Bot
├── artifacts/    weights, prompts, tables, whatever yours needs
└── README.md     one line on how it decides
```

Nothing to register anywhere. `--bot mine` finds it because the folder is there. A
prefix works too as long as it is unique, so `--bot mi` is fine until someone adds
`mine-v2`, at which point it becomes an error naming both rather than a guess.

**If your bot is a prompt around a language model**, add `--llm` and you start from the
shared harness instead of an empty `act`:

```bash
uv run pokelike bot new my-prompt --llm
```

You then write nothing but the prompt. The tools, the agentic loop, the state
rendering, the HTTP call and what happens when it fails all live in `pokelike.bot.llm`
and are shared by every LLM bot **on purpose**: two bots with different loops are two
harnesses being compared, and the model is the smaller half of that difference.

What it writes already plays, which matters more than it sounds: measure it before you
change a line, and when the number moves later you know it moved because of you.

```bash
uv run pokelike bot run --bot mine --runs 5 -d
uv run pokelike bot bench --bot mine --dry-run     # the real 50 seeds, recorded nowhere
```

## 4. Write it

The only method you must write is `act`. It gets the state and returns an index into
`state["actions"]`.

```python
from typing import Any

from pokelike.bot.base import Bot


class MyBot(Bot):
    name = "mine"

    def act(self, state: dict[str, Any]) -> int:
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

Everything the game knows is in `state`, including things nothing on screen tells you:
`team[i].move` is what that Pokemon actually attacks with, power and type included, and
`offered_moves` is what the move tutor would hand each of them.

**One class per folder.** The name of the folder says which bot ran, so a file defining
two of them is refused rather than guessed at.

That is the minimum. The optional hooks (`reorder`, `reason`, `reset`, `finish`,
`artifacts`) are documented in `pokelike.bot.base`; the second road where a model picks
the move (`LLMBot` and its knobs and seams) and how to ship your own `bridge.js` are
documented in `pokelike.bot.llm`.

## 5. Measure it

One measurement, the official benchmark: the 50 fixed seeds everyone is scored on.
There is deliberately no second protocol, because runs vary enormously by luck, so a
hand-picked seed set mostly measures who drew the nicer maps, and the same weights can
score 1.60 on one set and 1.10 on the official 50.

```bash
uv run pokelike bot bench --bot mine --dry-run                       # nothing recorded
uv run pokelike bot bench --bot mine --author YOUR-HANDLE --category rules
```

If yours calls a model, the credentials can come from flags instead of exports.
`--api-key @path` reads a file, so the key never reaches your shell history:

```bash
uv run pokelike bot bench --bot mine --dry-run \
  --endpoint https://openrouter.ai/api --api-key @~/.key --model openai/gpt-4o-mini
```

> **Easy to get wrong, and now it cannot be.** Only a **complete** run records a
> result. `--runs N` is a practice run by definition, since a score over 5 seeds is not
> comparable to one over 50, and `--dry-run` plays all 50 and records nothing. Neither
> leaves anything behind for a stray `git add` to pick up.

A recorded result lands in `bots/mine/result.json`, next to the code that earned it,
with a fingerprint over both. If you then edit the bot, the table marks the row **⚠︎**
until you measure it again: a score can never quietly describe code that no longer
exists.

## 6. Submit

You forked in step 1, so `origin` is your fork and there is nothing left to set up:

```bash
git checkout -b my-bot
git add bots/mine
git commit -m "Add my-bot"
git push origin my-bot
```

Then open the pull request GitHub offers you, from your fork to this repo. Your whole
submission is one folder. A pull request that touches only `bots/` is read as a
submission and usually merged as is; one that also changes `src/` or `llm-bench/` gets a
slower read, because those are what makes every recorded score comparable, that is
[Part 2](#part-2-changing-the-repo-itself). Everything you are allowed to change lives
inside your own folder, down to the JavaScript that decides what the state contains.

---

# Part 2: Changing the repo itself

This part is about the **repository**: bugs, the shared library, and the model
benchmark. If you only want to build a bot, you are done, everything you need is
Part 1, and a bot needs nothing from here.

- [Found a bug](#found-a-bug)
- [What lands how](#what-lands-how)
- [Why `llm-bench/` is closed](#why-llm-bench-is-closed)
- [The one file to be careful with](#the-one-file-to-be-careful-with)
- [Proposing a new harness](#proposing-a-new-harness)
- [Running the tests](#running-the-tests)

## Found a bug

Open an issue. This is the most useful thing anyone does here.

Bugs in the shared library are hard to see from the inside, and the person best placed
to notice one is somebody using it for real: building a bot, reading what their model
was actually sent, and finding that it was not what the documentation said. If you spot
that, say so even if you are not sure.

What helps in an issue:

- what you expected the model or the CLI to receive, and what it received
- a seed and a step, if you have one. `pokelike bot run --bot random --runs 1 -d` prints
  every decision with the screen it was made on
- whether you have a fix. If you do, say so and it will usually be taken as a patch

## What lands how

| a pull request touching | is read as | usually |
|---|---|---|
| only `bots/` | a submission | merged as is |
| `src/` | a change to the shared library | reviewed for what it means to recorded rows, sometimes landed as a patch |
| `llm-bench/*/harness/` of an existing version | an edit to a frozen file | refused, with a pointer to a new version |
| a new `llm-bench/v<n>/` | a new question to ask models | discussed on its merits |
| `llm-bench/*/results/` | a hand-edited result | refused |

`src/pokelike/` is the shared library. The CLI reads it, every bot reads it, and three
of its files (`browser.py`, `game.py`, `runner.py`) are hashed into every recorded
benchmark result because they drive the game. A change there is welcome and just needs
to be read carefully; a change that comes with a test showing what it fixes is much
easier to land.

Results are written by the benchmark, never by hand. If a recorded number is wrong, the
run was wrong: say so in an issue rather than correcting the file.

## Why `llm-bench/` is closed

The benchmark makes one claim: a row says something about the **model** rather than
about whoever tuned the scaffold hardest. That holds only if every model was asked the
same question, so the scaffold cannot move.

Each version under `llm-bench/<v>/harness/` therefore freezes four files, and none is
edited once a result exists beside it:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

Three files are shared instead of copied, because freezing them would mean each harness
carrying its own browser plumbing: `browser.py`, `game.py` and `runner.py`. They are
hashed into every result, so a change is reported rather than absorbed.

Every result records a sha256 of all seven, plus the name and hash of the game bundle,
taken **before the first seed is played**. The table marks a row when any of them stops
matching what is on disk. A continuous integration check refuses a pull request that
edits a frozen file with results beside it, so you find out on the pull request rather
than in review.

`bridge.js` is frozen for a stronger reason than the renderer, and it is worth
understanding: a bot answers with an **index** into `actions`, so reordering that list
does not change what the model sees, it changes what its answer means.

## The one file to be careful with

`init.js` replaces `Math.random` and pins `Date.now`, and a run's seed is built from
both. Changing a constant in it does not mark recorded scores as stale, it **voids**
them: every seed maps to a different run, and the benchmark carries on answering, about
a game nobody else can replay.

If you have a reason to touch it, that is an issue and a conversation, not a pull
request.

## Proposing a new harness

A better scaffold is a new directory, not edits to an old one. `v0`'s rows stay valid
under `v0`.

Start with an issue saying what you would ask a model and why. That is what a version
is. Say what you expect before it runs, so the README cannot be adjusted to fit the
number afterwards.

The mechanics are small. Copy the four frozen files into `llm-bench/v<next>/harness/`,
change them there, and nothing else needs editing: versions are discovered on disk, and
whether a harness lets the model keep notes between runs is asked of the harness rather
than configured.

## Running the tests

```bash
uv run pytest -q                    # everything, about a minute
uv run pytest -q -m "not slow"      # skips the ones that drive a browser
```

The suite needs the game on disk. `pokelike setup` mirrors it; without it the tests
that touch the engine skip themselves and the run goes green having checked nothing.
