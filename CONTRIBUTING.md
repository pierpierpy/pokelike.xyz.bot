# Contributing

This page is about the **repository**: bugs, the shared library, and the model
benchmark.

If you want to build a bot, you are in the wrong file. Everything about that is in
[GUIDE.md](GUIDE.md), and a bot needs nothing from here: one folder in `bots/`, one
pull request, and inside that folder the rules are yours.

---

**Contents**

- [Found a bug](#found-a-bug)
- [What lands how](#what-lands-how)
- [Why `llm-bench/` is closed](#why-llm-bench-is-closed)
- [The one file to be careful with](#the-one-file-to-be-careful-with)
- [Proposing a new harness](#proposing-a-new-harness)
- [Running the tests](#running-the-tests)

---

## Found a bug

Open an issue. This is the most useful thing anyone does here.

Bugs in the shared library are hard to see from the inside, and the person best
placed to notice one is somebody using it for real: building a bot, reading what
their model was actually sent, and finding that it was not what the documentation
said. If you spot that, say so even if you are not sure.

What helps in an issue:

- what you expected the model or the CLI to receive, and what it received
- a seed and a step, if you have one. `pokelike bot --bot random --runs 1 -d` prints
  every decision with the screen it was made on
- whether you have a fix. If you do, say so and it will usually be taken as a patch

Bug reports about the shared code are welcome even though changing that code needs a
conversation. Those are not in tension: the report is what is wanted, and the
conversation is only about how the change lands without breaking numbers recorded
months ago.

## What lands how

| a pull request touching | is read as | usually |
|---|---|---|
| only `bots/` | a submission | merged as is |
| `src/` | a change to the shared library | reviewed for what it means to recorded rows, sometimes landed as a patch |
| `llm-bench/*/harness/` of an existing version | an edit to a frozen file | refused, with a pointer to a new version |
| a new `llm-bench/v<n>/` | a new question to ask models | discussed on its merits |
| `llm-bench/*/results/` | a hand-edited result | refused |

`src/pokelike/` is the shared library. The CLI reads it, every bot reads it, and
three of its files (`browser.py`, `game.py`, `runner.py`) are hashed into every
recorded benchmark result because they drive the game. A change there is welcome and
just needs to be read carefully; a change that comes with a test showing what it
fixes is much easier to land.

Results are written by the benchmark, never by hand. If a recorded number is wrong,
the run was wrong: say so in an issue rather than correcting the file.

## Why `llm-bench/` is closed

The benchmark makes one claim: a row says something about the **model** rather than
about whoever tuned the scaffold hardest. That holds only if every model was asked
the same question, so the scaffold cannot move.

Each version under `llm-bench/<v>/harness/` therefore freezes four files, and none is
edited once a result exists beside it:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

Three files are shared instead of copied, because freezing them would mean each
harness carrying its own browser plumbing: `browser.py`, `game.py` and `runner.py`.
They are hashed into every result, so a change is reported rather than absorbed.

Every result records a sha256 of all seven, plus the name and hash of the game
bundle, taken **before the first seed is played**. The table marks a row when any of
them stops matching what is on disk. A continuous integration check refuses a pull
request that edits a frozen file with results beside it, so you find out on the pull
request rather than in review.

`bridge.js` is frozen for a stronger reason than the renderer, and it is worth
understanding: a bot answers with an **index** into `actions`, so reordering that list
does not change what the model sees, it changes what its answer means.

## The one file to be careful with

`init.js` replaces `Math.random` and pins `Date.now`, and a run's seed is built from
both. Changing a constant in it does not mark recorded scores as stale, it **voids**
them: every seed maps to a different run, and the benchmark carries on answering,
about a game nobody else can replay.

If you have a reason to touch it, that is an issue and a conversation, not a pull
request.

## Proposing a new harness

A better scaffold is a genuinely interesting contribution, and the way in is a new
directory rather than edits to an old one. `v0`'s rows stay valid under `v0`.

Start with an issue saying what you would ask a model and why, because that is the
whole substance of a version. Say what you expect to happen before it runs: a harness
README that predicts a result and is then measured is worth more than one that
explains a number afterwards.

The mechanics are small. Copy the four frozen files into
`llm-bench/v<next>/harness/`, change them there, and nothing else needs editing:
versions are discovered on disk, and whether a harness lets the model keep notes
between runs is asked of the harness rather than configured.

## Running the tests

```bash
uv run pytest -q                    # everything, about a minute
uv run pytest -q -m "not slow"      # skips the ones that drive a browser
```

The suite needs the game on disk. `pokelike setup` mirrors it; without it the tests
that touch the engine skip themselves and the run goes green having checked nothing.
