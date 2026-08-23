# Contributing

This guide has two parts, and most people only need the first. Part 1 covers writing
and submitting a bot: six steps from a clone to a pull request. Part 2 covers changing
the repository itself: fixing a bug, changing the shared library, or adding a new
benchmark harness. A bot needs nothing from Part 2: one folder under `bots/`, one pull
request, and inside that folder the rules are yours.

---

**Contents**

- [Part 1: Write and submit a bot](#part-1-write-and-submit-a-bot)
  - [What counts as a bot](#what-counts-as-a-bot)
  - [Where to experiment](#where-to-experiment)
  - The six steps: [1 Set up](#1-set-up-once) · [2 See the state](#2-look-at-what-a-bot-receives) · [3 Create it](#3-create-it) · [4 Write it](#4-write-it) · [5 Measure it](#5-measure-it) · [6 Submit](#6-submit)
- [Part 2: Changing the repo itself](#part-2-changing-the-repo-itself)
  - [Found a bug](#found-a-bug)
  - [What lands how](#what-lands-how)
  - [Naming in the shared library](#naming-in-the-shared-library)
  - [Why `llm-bench/` is closed](#why-llm-bench-is-closed)
  - [The one file to be careful with](#the-one-file-to-be-careful-with)
  - [Proposing a new harness](#proposing-a-new-harness)
  - [Running the tests](#running-the-tests)

---

# Part 1: Write and submit a bot

This part covers two things first, what qualifies as a bot and where to try ideas out,
then walks through six steps from a clone to a pull request. Everything beyond the
minimum, including the optional hooks, the LLM harness knobs and seams, and shipping
your own `bridge.js`, is documented in the classes you inherit from:
`pokelike.bot.base.Bot` and `pokelike.bot.llm.LLMBot`.

## What counts as a bot

A bot is anything that picks a move given the state: a prompt around an LLM, a model
fine-tuned on the game, reinforcement learning of any flavour, a hand-written rulebook,
a search over the game tree (the engine ships a battle simulator you can call), or
something fully deterministic, if you can find one that works. If it turns a state into
an index, it qualifies. Entries are ranked by badges, the game's own progress counter,
and the standings are in [bots/README.md](bots/README.md).

## Where to experiment

The `experiments/` directory is a scratch area: nothing you add there is tracked by
default, so a pull request that adds a bot cannot drag a training run along with it.
Copy the closest example, work there, and measure the candidate right where it lives:

```bash
cp -r experiments/example experiments/mine
uv run python -m experiments.example.train --episodes 20
uv run pokelike bot bench --bot experiments/mine --dry-run   # by path, records nothing
```

When it earns its place, bring it into `bots/` the standard way described in step 3,
and benchmark it there under its own name.
[experiments/README.md](experiments/README.md) walks through the whole research area.
In short: you show what your bot does, not how you arrived at it.

## 1. Set up, once

Fork this repo on GitHub first, and clone the fork you just created rather than this
original repository. That way `origin` points somewhere you can push to, which is what
step 6 needs:

```bash
git clone https://github.com/YOUR-HANDLE/pokelike.xyz.bot && cd pokelike.xyz.bot
uv sync
uv run pokelike setup          # the browser plus an offline copy of the game, ~130 MB
```

The copy is offline on purpose: after this step, nothing you do reaches the internet,
and the same seed always replays the same run.

## 2. Look at what a bot receives

Do not guess at what a bot receives. The reference below is generated from a live
observation, so it cannot describe a game that no longer exists:

```bash
uv run pokelike schema         # the full reference
uv run pokelike play           # play it yourself; three minutes is enough
```

Two things decide how you write everything else.

The state is one dict, not a history. What history matters is already inside it: every
map node carries a `visited` flag, and `stats` are cumulative from the start of the run.

The indices change every turn: `state["actions"]` is the list you choose from, and
index 2 might be a battle now and a catch next turn. Nothing can be decided by
position; look at what each entry actually is.

It is worth watching a trained bot play before you write anything: pick whichever one
is leading in [the standings](bots/README.md), and run it:

```bash
uv run pokelike bot run --bot sarsa-v2 --seed 40003 --runs 1 -g -dd
```

The `-g` flag draws the map beside each decision; the `-dd` flag prints the value it
gave every option before choosing.

## 3. Create it

```bash
uv run pokelike bot new mine
```

Running that command creates a folder, and the folder is the bot:

```
bots/mine/
├── bot.py        one class inheriting from Bot
├── artifacts/    weights, prompts, tables, whatever yours needs
└── README.md     one line on how it decides
```

There is nothing to register anywhere: passing `--bot mine` finds it because the
folder is there. A prefix works too, as long as it is unique, so `--bot mi` resolves
fine until someone adds `mine-v2`; at that point it becomes an error naming both bots
rather than a silent guess.

If your bot is a prompt around a language model, add `--llm` and you start from the
shared harness instead of an empty `act`:

```bash
uv run pokelike bot new my-prompt --llm
```

You then write nothing but the prompt. The tools, the agentic loop, the state
rendering, the HTTP call, and what happens when a call fails, all live in
`pokelike.bot.llm` and are shared by every LLM bot on purpose: two bots with different
loops are really two different harnesses being compared, and the model becomes the
smaller half of that difference.

What `bot new --llm` writes already plays a full game, which matters more than it
sounds: measure it before you change a single line, so that when the number moves
later, you know it moved because of you.

```bash
uv run pokelike bot run --bot mine --runs 5 -d
uv run pokelike bot bench --bot mine --dry-run     # the real 50 seeds, recorded nowhere
```

## 4. Write it

The only method you are required to write is `act`. It receives the state and returns
an index into `state["actions"]`.

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
the `team[i].move` field is what that Pokemon actually attacks with, power and type
included, and `offered_moves` is what the move tutor would hand each of them.

Keep one class per folder: the name of the folder says which bot ran, so a file defining
two of them is refused rather than guessed at.

That is the minimum required. The optional hooks (`reorder`, `reason`, `reset`,
`finish`, `artifacts`) are documented in `pokelike.bot.base`. The alternative path,
where a model picks the move (`LLMBot` and its knobs and seams), and how to ship your
own `bridge.js`, are documented in `pokelike.bot.llm`.

## 5. Measure it

There is exactly one measurement, the official benchmark: the 50 fixed seeds everyone
is scored on. There is deliberately no second protocol, because runs vary enormously by
luck, so a hand-picked seed set mostly measures who drew the nicer maps. The same
weights can score 1.60 on one set and 1.10 on the official 50.

```bash
uv run pokelike bot bench --bot mine --dry-run                       # nothing recorded
uv run pokelike bot bench --bot mine --author YOUR-HANDLE --category rules
```

If yours calls a model, the credentials can come from flags instead of exports. The
`--api-key @path` form reads the key from a file, so it never reaches your shell
history:

```bash
uv run pokelike bot bench --bot mine --dry-run \
  --endpoint https://openrouter.ai/api --api-key @~/.key --model openai/gpt-4o-mini
```

> This used to be easy to get wrong; now it cannot be. Only a complete run records a
> result. Running with `--runs N` is a practice run by definition, since a score over 5
> seeds is not comparable to one over 50, and `--dry-run` plays all 50 seeds and records
> nothing. Neither one leaves anything behind for a stray `git add` to pick up.

A recorded result lands in `bots/mine/result.json`, next to the code that earned it,
with a fingerprint over both. If you then edit the bot, the table marks the row with
`⚠︎` until you measure it again: a score can never quietly describe code that no longer
exists.

## 6. Submit

You forked in step 1, so `origin` is your fork and there is nothing left to set up:

```bash
git checkout -b my-bot
git add bots/mine
git commit -m "Add my-bot"
git push origin my-bot
```

Then open the pull request that GitHub offers you, from your fork to this repository.
Your whole submission is one folder. A pull request that touches only `bots/` is read
as a submission and is usually merged as is. One that also changes `src/` or
`llm-bench/` gets a slower read, because those are what make every recorded score
comparable; that process is covered in
[Part 2](#part-2-changing-the-repo-itself). Everything you are allowed to change lives
inside your own folder, down to the JavaScript that decides what the state contains.

---

# Part 2: Changing the repo itself

This part covers the repository itself: bugs, the shared library, and the model
benchmark. If you only want to build a bot, you are already done: everything you need
is in Part 1, and a bot needs nothing from here.

- [Found a bug](#found-a-bug)
- [What lands how](#what-lands-how)
- [Naming in the shared library](#naming-in-the-shared-library)
- [Why `llm-bench/` is closed](#why-llm-bench-is-closed)
- [The one file to be careful with](#the-one-file-to-be-careful-with)
- [Proposing a new harness](#proposing-a-new-harness)
- [Running the tests](#running-the-tests)

## Found a bug

Open an issue. This is the most useful thing anyone does here.

Bugs in the shared library are hard to see from the inside, and the person best placed
to notice one is somebody using it for real: building a bot, reading what their model
was actually sent, and finding that it was not what the documentation said. If you spot
something like that, say so, even if you are not sure.

What helps in an issue:

- what you expected the model or the CLI to receive, and what it received
- a seed and a step, if you have one. Running `pokelike bot run --bot random --runs 1
  -d` prints every decision along with the screen it was made on
- whether you have a fix. If you do, say so and it will usually be taken as a patch

## What lands how

| a pull request touching | is read as | usually |
|---|---|---|
| only `bots/` | a submission | merged as is |
| `src/` | a change to the shared library | reviewed for what it means to recorded rows, sometimes landed as a patch |
| `llm-bench/*/harness/` of an existing version | an edit to a frozen file | refused, with a pointer to a new version |
| a new `llm-bench/v<n>/` | a new question to ask models | discussed on its merits |
| `llm-bench/*/results/` | a hand-edited result | refused |

The `src/pokelike/` package is the shared library. The CLI reads it, every bot reads
it, and three of its files (`browser.py`, `game.py`, `runner.py`) are hashed into every
recorded benchmark result because they drive the game. A change there is welcome and
just needs to be read carefully; a change that comes with a test showing what it fixes
is much easier to land.

Results are written by the benchmark, never by hand. If a recorded number is wrong, the
run was wrong: say so in an issue rather than correcting the file.

## Naming in the shared library

The codebase already follows one naming convention everywhere, and a change to `src/`
is expected to follow it too rather than introduce a new one.

A Python file is always snake_case, a class is always PascalCase, and a well-known
acronym inside a class name stays fully capitalized rather than being title-cased, so
the class is `LLMBot`, not `LlmBot`. A function or method name is snake_case. A
module-level constant meant to be fixed for the life of the program is
SCREAMING_SNAKE_CASE, such as `STANDARD_SEEDS` or `HEARTBEAT_SECS`. A single leading
underscore marks a name that is not part of the public interface: a helper function
used only inside its own module, a private method, or a small helper class. A module
is free to import another module's underscore-prefixed name when both live in the same
package and duplicating the helper would be worse than sharing it, but that name still
carries no promise of staying the same across a version and should not be imported
from outside the package.

A boolean field on a config object is a bare noun or adjective, never prefixed with
`is_` or `use_`, so the field is `bag_tool`, not `use_bag_tool`. A field that caps or
limits something ends in the unit it measures: `notes_cap` for a count, `note_chars`
for a character limit, `max_tokens` for a token ceiling. Across every config in this
codebase, setting one of these fields to zero turns the feature off, and setting it to
negative one means unlimited; a new field that caps something should follow the same
two special cases rather than inventing a third.

A CLI flag is kebab-case, such as `--dry-run` or `--api-key`, and is left to convert
to its snake_case Python name automatically; an explicit `dest=` is only added when
that automatic conversion would give the wrong name, or when two flags need to write
to the same one. A bot folder or an experiment folder is kebab-case, such as
`sarsa-v2` or `llm-example2`; a package under `src/pokelike/` is a bare, singular
noun in snake_case, such as `core`, `bot`, or `harness`.

The words themselves matter as much as the casing. What a person reads when the CLI
prints the ranked results is always called the standings; `leaderboard` is the name of
the Python module that builds that table, not a word to use in anything a user reads.
The frozen bundle under `llm-bench/<version>/harness/` is always called the harness,
never the scaffold; `scaffold` is reserved for the literal `arena/scaffold.py`
template generator and for a bot's own, non-frozen prompt and tools, which is a
different thing from the frozen harness and should read as different. A pass is one
sweep through the fifty standard seeds for one model; a run is one game played on one
seed from start to finish; a fingerprint is the hash tying a recorded result to the
exact code that produced it. Reuse these six words for these six concepts everywhere,
rather than finding a new way to say the same thing.

Every module opens with a docstring that states its purpose in one sentence, and adds
a blank line and a short paragraph of detail only when the one sentence is not enough
on its own.

## Why `llm-bench/` is closed

The benchmark makes one claim: a row says something about the model, rather than about
whoever tuned the harness hardest. That claim holds only if every model is asked the
same question, so the harness cannot move.

Each version under `llm-bench/<v>/harness/` therefore freezes four files, and none is
edited once a result exists beside it:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

Three files are shared instead of copied, because freezing them would mean every
harness had to carry its own browser plumbing: `browser.py`, `game.py`, and
`runner.py`. They are hashed into every result, so a change to them is reported rather
than silently absorbed.

Every result records a sha256 hash of all seven files, plus the name and hash of the
game bundle, taken before the first seed is played. The table marks a row when any of
them stops matching what is on disk. A continuous integration check refuses a pull
request that edits a frozen file that already has results beside it, so you find out
from the pull request itself rather than during review.

The `bridge.js` file is frozen for a stronger reason than the renderer, and it is worth
understanding why: a bot answers with an index into `actions`, so reordering that list
does not change what the model sees, it changes what its answer means.

## The one file to be careful with

The `init.js` file replaces `Math.random` and pins `Date.now`, and a run's seed is
built from both. Changing a constant in it does not mark recorded scores as stale, it
voids them entirely: every seed then maps to a different run, and the benchmark
carries on answering questions about a game nobody else can replay.

If you have a reason to touch it, that is an issue and a conversation, not a pull
request.

## Proposing a new harness

A better harness is a new directory, not edits to an old one. `v0`'s rows stay valid
under `v0`.

Start with an issue saying what you would ask a model and why. That is what a version
is. Say what you expect before it runs, so the README cannot be adjusted to fit the
number afterwards.

The mechanics are small. Copy the four frozen files into `llm-bench/v<next>/harness/`,
change them there, and nothing else needs editing: versions are discovered on disk, and
whether a harness lets the model keep notes between runs is decided by the harness
itself, not configured externally.

## Running the tests

```bash
uv run pytest -q                    # everything, about a minute
uv run pytest -q -m "not slow"      # skips the ones that drive a browser
```

The suite needs the game to be on disk; running `pokelike setup` provides it. Without
it, the tests that touch the engine skip themselves, and the run goes green having
checked nothing.
</content>
