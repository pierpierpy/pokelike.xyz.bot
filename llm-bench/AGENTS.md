# AGENTS.md, llm-bench/

Details for the model benchmark. The tour is [README.md](README.md); the cross-cutting
internals are in the root [AGENTS.md](../AGENTS.md); each version's own README says what
that version asks a model.

- [What this measures, and why it is frozen](#what-this-measures-and-why-it-is-frozen)
- [The seven-key fingerprint](#the-seven-key-fingerprint)
- [The harness is a copy, not a subclass](#the-harness-is-a-copy-not-a-subclass)
- [What each version asks](#what-each-version-asks)
- [Cross-run memory](#cross-run-memory)
- [What a pass writes, and where](#what-a-pass-writes-and-where)
- [What the fingerprint does not cover](#what-the-fingerprint-does-not-cover)
- [In Docker](#in-docker)

---

## What this measures, and why it is frozen

A row here claims something about the **model**, not about whoever tuned the scaffold
hardest. That holds only if every model was asked the same question, so the scaffold
cannot move. **Nothing in `llm-bench/*/harness/` is editable once a result exists beside
it.** An improvement is a new directory; the old rows stay valid under the version where
they were earned, which is why the version is in the path and not in a variable. A CI
check refuses a pull request that edits a frozen file with results beside it.

Each version freezes four files, and they are not equally dangerous:

| file | decides | if you change it |
|---|---|---|
| `bot.py` | the loop, the prompt, the tools | marks recorded rows stale |
| `render.py` | the text the model reads | marks rows stale |
| `bridge.js` | what is in the state, and the **order** `actions` come in | marks rows stale, and worse than the renderer, because a bot answers with an *index*, so reordering the list does not change what the model sees, it changes what its answer **means** |
| `init.js` | the seeded `Math.random` and the pinned clock | **voids** the rows: the run seed is `Date.now() ^ (Math.random() * 2**32)`, so moving a constant maps every seed to a different run and the benchmark carries on answering about a game nobody else can replay |

Three more files are **shared and hashed** rather than copied, because freezing them
would mean each version carrying its own browser plumbing: `browser.py`, `game.py`,
`runner.py`. A change to them is reported, not absorbed.

## The seven-key fingerprint

`fingerprints(version)` produces seven sha256 hashes (each truncated to 16 hex chars),
taken **before the first seed is played**, against the code about to run, not whatever
is on disk when the pass ends, so an edit part way through cannot certify code it never
ran:

- frozen, under `llm-bench/<v>/harness/`: `bot.py`, `render.py`, `bridge.js`, `init.js`
- shared, at their source locations: `shared/browser.py`, `shared/game.py`,
  `shared/runner.py`

Plus the **game bundle**, recorded separately by name and hash because it is downloaded
rather than committed and an upstream release changes it.

The comparison in `stats()` is **key by key**, over only the keys a pass actually
recorded (`any(now[k] != v for k, v in used.items() if k in now)`). Whole-dict equality
was wrong: the day you add a key to `fingerprints()`, every prior result would acquire a
key it could not have carried and every row would declare its code changed. That change
had to land first, because it is what let the fingerprint grow from two keys to seven
without marking anything.

`record()` writes to `llm-bench/<v>/results/<slug>.json`, appending each pass to the
existing doc, and stores the fingerprint **per pass**: a pass played before `render.py`
changed and one played after are different measurements. `records(seeds)` returns true
only for the standard fifty **by value and order**, under a harness that carries notes
between runs, the order the seeds were played in is part of what was measured, so a set
of one's own choosing cannot be recorded.

## The harness is a copy, not a subclass

`llm-bench/v0/harness/bot.py` reads `class HarnessV0(Bot)`, it inherits from `Bot`, not
`LLMBot`, and `from pokelike.bot.llm import` appears zero times. So `choose` and
`rearrange` there are not overrides, they are independent, parallel implementations of
the LLM loop. They resemble `src/pokelike/bot/llm.py` only because the second was born
from the first; they do not talk to each other.

The reason is the whole point of freezing: the shared `bot/llm.py` **must** improve,
because `bots/` reads it. If a frozen harness imported it, the next improvement for a
submission would silently change what every recorded score meant.

**Two import paths are frozen too:** `pokelike.arena.leaderboard.Artifact` and
`pokelike.bot.base.Bot`. All four harnesses import them, as do submitted bots whose
files are fingerprinted against their scores. Moving either means re-fingerprinting every result that records it, which is what the
move of `leaderboard.py` into `pokelike.arena` required.

## What each version asks

| | loop | memory | sees | tokens |
|---|---|---|---|---|
| `v0` | one call a turn, 4 tools, 4 rounds | last 6 moves, within the run | the screen | 1500 |
| `v2` | plus the last 3 turns carried verbatim, a `plan` tool, 6 rounds | plus 12 notes surviving the run (`remember`/`revise`/`forget`) | v0 | 4000 |
| `v4` | v2 | v2's notes, and the prompt now ASKS for them with examples; cap settable with `--set notes=N` | plus the node tooltips a person reads on hover, and the tutor block only at a tutor | 4000 |

`v1` (the notebook alone) and `v3` (the tooltips alone) were deleted, both unmeasured;
what v3 changed lives in v4. The numbers are not compacted: `HARNESS` is written into
every result, and `v3` carried `HARNESS = 4` while it existed, so the generation number
and the directory number do not coincide.

`v0`'s prompt holds facts and no strategy on purpose: advice in a prompt measures how
well models follow *our* advice. `v2` breaks that deliberately, because measurement
forced it, under v0's prompt two models played fifty runs each and called `remember`
zero times, and "memory does not help" and "the models never used it" are different
findings. So v0 and v2 ask genuinely different questions and their rows are never ranked
together.

One trap when generating the next version from the last: `self.memory` is the
journal-trim size, `MEMORY` the count of past moves; the notes are `self.notebook`, the
plan `self.plan`, the carried exchanges `self.scratch`. Every harness after v0 was
generated mechanically from the one before, and each time the rename was where the bugs
were, a leftover `HarnessV2` in `v3` was found by the test suite, not by reading.

## Cross-run memory

`cross_run_memory(version)` loads the harness class and reads its `CROSS_RUN_MEMORY`
attribute, it is asked of the harness, never hardcoded, so adding a version needs no
edit in `harness/llmbench.py` or `run.sh`. It controls three things:

- **`--workers` is refused** when true: notes from one run feed the next, so the runs are
  not independent and splitting seeds across workers would give each its own notebook.
- **The `learn` and `notes` columns appear**: `learn` is the last ten runs of a pass
  minus its first ten, in play order, which is only meaningful when the model carries
  something between runs.
- The pass log opens the notebook and plan files.

## What a pass writes, and where

One directory per command, `llm-bench/<version>/logs/<stamp>/`:

| file | what it holds |
|---|---|
| `command.json` | what was asked: harness, models, seeds, workers, repeat, endpoint. **Never a credential**, `record_command` refuses a payload with a credential-shaped key |
| `<model>-passN.log` | one line per finished run, flushed as it happens. What you `tail -f` |
| `<model>-passN.jsonl` | one object per decision: a wall clock, the option taken, the options it had, the reason, every tool call in order, the team, the map when it changed, and tokens at turn/run/pass level. No prompts, reconstructible from the harness plus the seed |
| `<model>-passN-notebook.log` | under any harness that keeps notes, opened on demand; the notes as they stood at the end of each run, `unchanged` when nothing moved |
| `<model>-passN-plan.log` | same, for the route it planned for each map |

Every harness records its own tool calls, in its own dispatch loop, because `play` and
`set_lead` never reach `run_tool` and nothing outside the harness can see them; a version
without `tool_calls_made()` fails the suite.

Results live **apart**, in `results/<model>.json`, one file per model with every pass
appended, that is the comparable record, and ten commands over three days build one
model's history. Logs are gitignored, and every statistic in the table is derived from
the rows at print time, so nothing recomputable is stored (which is why cost is never
written into a result), and regenerating the table after recording or deleting anything
is on you.

## What the fingerprint does not cover

- **The seed list**, recorded as data in every pass rather than hashed, so it is
  checkable by reading.
- **`src/pokelike/harness/llmbench.py`**, it builds the bot and drives the pass, and
  a change there is not reported. Treat it the way you would treat the frozen files and
  say what you did in the pull request.
- Two open holes worth knowing: the three shared keys are absent from the eleven results
  recorded before the scripts were extracted (writing today's hashes for an old run
  would be false, so they stay unregistered = unverified), and `STATE_VIEW = "json"` on
  an old harness rerun would expose fields added after it was frozen (no recorded result
  used anything but `"screen"`).

## In Docker

Long passes run in the container so they cannot notice a library upgrade, a Chromium
update, or a laptop sleeping. The build context is the **repo root** and
`.dockerignore` must stay there. Three things that are not optional:

- **The game is not downloaded**, it is your `site/` mounted read-only (`site/` is in
  `.dockerignore`), so the image stays small and the container plays the copy you
  verified.
- **`shm_size: 2gb`**, Docker gives a container 64 MB of shared memory and Chromium
  wants far more; without it browsers die mid-run with errors that read like the game
  crashed.
- **Only `llm-bench/` is writable**, the image could run any `pokelike` command, so
  without that restraint a stray `bench --bot sarsa-v2` would record a result inside the
  container and lose it on exit.

`run.sh` builds, runs detached, names the container after the model (which is how
`model watch` and `watch --all` know what is running), picks the worker count the
harness allows, and removes it when done. Credentials come from `.env`.
