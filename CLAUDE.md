# CLAUDE.md, pokelike.xyz.bot

Notes for agents working on this repo.

**Read [README.md](README.md) as well.** It explains what the project does, how
it is installed and how it is used, everything you need to guide a user. This
file only adds what someone *changing* the code needs: internals, pitfalls, and
the reasoning behind decisions that look odd.

**Orientation**
[What this is](#what-this-is) ·
[Commands](#commands) ·
[Architecture](#architecture)

**How it works**
[Talking to the game](#talking-to-the-game) ·
[Scoring](#scoring) ·
[Reproducibility](#reproducibility) ·
[Performance](#performance)

**Before you change anything**
[Real pitfalls](#real-pitfalls) ·
[Tests](#tests) ·
[Submissions](#submissions) ·
[Secrets](#secrets)

---

## What this is

An environment for letting bots play [pokelike.xyz](https://pokelike.xyz/), a
Pokémon roguelike that runs entirely in the browser. The game has no backend: all
its logic is in one obfuscated JavaScript bundle. We run it in headless Chromium
and talk to its global functions.

## Commands

```bash
uv sync                          # environment
uv run pokelike setup            # browser + offline copy (once)
uv run pokelike play --seed 42   # interactive run
uv run pokelike bot --runs 5     # the random bot
uv run pokelike history -d       # what you played here, columns explained
uv run pokelike schema           # what a bot receives (--markdown regenerates it in README.md)
uv run pokelike bot -d --runs 1  # log every decision, for any bot
uv run pytest                    # full suite, ~1 minute
uv run pytest -m "not slow"      # fast tests only, no browser

uv run pokelike bench --bot random             # the standard benchmark, 50 seeds
uv run pokelike bench --bot random --dry-run   # ... without writing an entry
uv run pokelike leaderboard                    # rebuild the standings from disk

uv run pokelike new-bot mine                   # a bot folder that already plays
uv run pokelike new-bot mine --llm             # ... starting from the LLM harness

uv run pokelike llm-bench --harness v0 --model a/b   # a model vs a FROZEN harness
uv run pokelike llm-bench --table                    # what has been measured
# credentials: $FW_ENDPOINT/$FW_TOKEN/$MODEL_ID, or --endpoint/--api-key/--model
# (--api-key @path reads a file, keeping the key out of ps and shell history)

uv run python -m experiments.example.train --episodes 20     # the shape of one
uv run python -m experiments.sarsa.train --episodes 300      # the real thing
uv run pokelike bench --bot experiments/mine --dry-run       # measure a candidate
```

## Architecture

```
site/                    the downloaded game (gitignored, ~130 MB)
src/pokelike/
├── core/                SHARED LOGIC, the only part that knows how to play
│   ├── bridge.js          injected into the page: observes and acts
│   ├── browser.py         Playwright headless, pinned seed, flattened animations
│   ├── game.py            class Game: reset/state/step/score/reorder
│   └── render.py          ASCII map, team, actions
├── bot/                 WHAT RUNS A BOT, not the bots themselves
│   ├── base.py            abstract Bot: only choose() is required
│   ├── catalogue.py       finds and loads a bot from its folder in bots/
│   ├── llm.py             the harness every llm-* bot shares: tools, agentic
│   │                      loop, HTTP, fallback policy. Shared so that a
│   │                      benchmark of models holds the harness still
│   └── random_bot.py      the baseline. Here rather than only in bots/random/
│                          because compare() defaults to it, so it has to work
│                          in a checkout with no bots/ at all
├── assets/
│   ├── mirror.py          builds site/ in five phases
│   └── server.py          serves site/ from disk
├── stats/registry.py    SQLite in stats/runs.db
├── bench.py             the standard 50-seed benchmark
├── runner.py            play_run(): the one loop that plays a run with a bot
├── schema.py            what a bot receives, described from a live state
├── scaffold.py          new-bot: writes a bot folder that already plays
├── leaderboard.py       reads bots/*/result.json, ranks, fingerprints
├── llmbench.py          the model benchmark: passes, fingerprints, tables, the
│                        parallel fan-out and the per-pass log
└── interfaces/          how something outside drives the game
    ├── cli/main.py        a human, in a terminal
    ├── api/server.py      a program, over HTTP
    └── python/            a script, a notebook or the REPL
        ├── driver.py        session(), open_game(), play(), compare()
        └── example.ipynb    the cell-by-cell walkthrough
llm-bench/               a MODEL benchmark, not a bot one: the harness is frozen
│                        and the model is the only thing that varies
├── docker/                the container long runs happen in. Build context is
│                          the REPO ROOT, and .dockerignore must stay there
├── v0/harness/bot.py      FROZEN copy of bot/llm.py. See the rule below
├── v1/harness/bot.py      v0 plus notes the model keeps between runs
└── v*/logs/<stamp>/       ONE DIRECTORY PER COMMAND: command.json, plus a .log
                           and a .jsonl of decisions per pass. Results stay one
                           file per model, outside, because that is the record
experiments/             research. OURS are tracked as worked examples; anything
│                        else anyone creates here is gitignored by default. One
│                        `!experiments/<name>/` line opts a folder in, and
│                        output/, logs/ and artifacts/ stay out regardless
├── env/                   the game as an RL problem: environment, rewards,
│                          encoding, tee() for per-experiment logs
├── example/               the smallest complete experiment
├── dyna-q/                tabular RL. LOST to random, and kept for that
├── sarsa/                 linear function approximation. The one that worked
└── llm/                   prompt strategies compared on identical seeds

Every experiment has the same shape: README, agent, train, output/, logs/. Keep
it that way when adding one. There is ONE way to measure a candidate, namely the
official benchmark, by path: `pokelike bench --bot experiments/mine --dry-run`.
Do not add per-experiment evaluation scripts with their own seed sets: a seed
set picked during development mis-ranks models (the same weights score 1.60 on
one such set and 1.10 on the official 50).

**An experiment is named after the bot it produces**, so `dyna-q/` → `dyna-q/`,
`sarsa/` → `sarsa-v1/` and `sarsa-v2/`, `llm/` → `llm-*/`. Hyphens work in a
folder name despite not being valid identifiers: `-m` takes a string and goes
through the path finder, so `python -m experiments.dyna-q.train` runs and the
relative imports inside it resolve. Only `import experiments.dyna-q` in source
is impossible, and nothing needs to write that.

The one thing NOT renamed with the folder is `trainer:` inside an already
recorded `artifacts/config.json`. It says `experiments/sarsa_lambda/train.py`
because that is what produced those weights. Rewriting a record to match a later
rename is what the fingerprint exists to prevent, and it would mark both rows
stale for a cosmetic edit.
bots/                    THE BOTS. One folder each: bot.py, artifacts/,
│                        result.json. Nothing registers them. The folder being
│                        there is what makes `--bot <name>` work
├── random/                the baseline, as a folder like everything else
├── dyna-q/                tabular RL. LOST to random, and kept for that
├── sarsa-v1/ sarsa-v2/    81 and 100 features. Both kept: the difference
│                          between them is what either result is evidence about
├── lspi/                  a contributed entry. sarsa-v2's features, weights
│                          solved as a fixed point instead of stepped toward
├── llm-baseline/ llm-survivor/ llm-explorer/ llm-analyst/
│                          one shared harness, four prompts. ~30 lines each
├── llm-raw/               llm-survivor's prompt, reading the raw state dict.
│                          One variable moved, so the pair means something
└── llm-example/           every knob turned, with reasons. Not benchmarked
tests/                   golden fingerprints + unit tests
tools/deobfuscate.py     makes the bundle readable (needs node)
```

Nothing in `src/` may import from `experiments/`: it is a scratch area, mostly
untracked, and the package cannot depend on files that are not in the clone.

**A bot is a folder, not a module.** `bots/<name>/bot.py` is loaded by path, so
it uses absolute imports (`from pokelike.bot.base import Bot`) and carries what
it needs in `artifacts/` beside it. It was relative imports that made the old
archived submissions unrunnable: we claimed they were self-contained and they
could not be executed from where they sat.

`result.json` lives in the same folder and holds a sha256 over `bot.py` and every
artifact. `pokelike leaderboard` recomputes it on read and marks a row stale when
they no longer match, so a score cannot describe code that has since changed. A
result with **no** fingerprint is reported as unchecked (`?`) rather than folded
into either bucket: calling it stale would be a claim we cannot support, calling
it clean would be the silence the fingerprint exists to prevent.

**Only three things are structural, and `bot/llm.py` is the awkward one.** The
test is whether something is built *on* or *competes*: `Bot` and `LLMBot` are
built on, `RandomBot` is the yardstick, everything else goes in `bots/`. But
`llm.py` being shared means editing it reaches every LLM bot ever measured.
exactly what self-containment exists to prevent, only from the other side. It is
shared anyway, because two bots with different loops are two harnesses being
compared and the model is the smaller half of that difference. `HARNESS` is what
keeps it honest: written into every result, flagged when it no longer matches.
**Bump it whenever a change there could move a decision.**

**Three things an LLM bot owns, and all three are recorded.** The prompt, the
state view (`STATE_VIEW` / `view()`), and the tools (`EXTRA_TOOLS` /
`run_tool()`). Each is a genuine experimental variable, so each goes into
`result.json` and into the standings, because two rows with different views are no more
comparable than two with different tools. `_situation()` deliberately is NOT the
hook: it owns the journal and the "pick an index" line, so replacing the view
cannot silently cost a bot its memory or drop the instruction. Keep that split.

**Bot names resolve by exact match, then unique prefix.** An ambiguous prefix is
an error naming the candidates, never a guess. `--bot sarsa` with both versions
on disk would otherwise benchmark one of them and produce a wholly plausible
number about the wrong bot.

`interfaces/` and `bot/` contain no game logic: they all go through `Game`'s five
methods. If you feel like putting a game rule in the CLI, it belongs in `core`.

Decision logging lives in `runner.play_run` for the same reason: recorded once,
in the shared loop, so a log means the same thing whatever is playing. Bots add
at most one line through the optional `explain()` hook.

`bot/` is deliberately not under `interfaces/`. The interfaces are entry points.
something outside drives the game through them. A bot is an extension point: you
write one, and the interfaces run it. Filing the concrete bots (random, llm,
dyna-q) under `interfaces/` would blur that.

## Talking to the game

The engine exposes everything as page globals. The useful ones:

| global | use |
|---|---|
| `state` | full state: team, bag, map (a DAG), badges, `runSeed` |
| `getAccessibleNodes(state.map)` | legal map moves |
| `onNodeClick(node)` | take a move |
| `runBattle(...)` | pure battle simulator, no DOM |
| `getBestMove`, `calcDamage` | the game's own AI and damage formula |
| `finalizeRunScore`, `foldBattleIntoRunStats`, `newRunStats` | scoring |
| `seedRng`, `getRngSeed` | internal PRNG |

No pixels are looked at. Screenshots exist (`Game.screenshot`) but are for humans
only.

Actions come in two kinds: map moves go through `onNodeClick(node)` (a direct
call), other choices activate a DOM element because that is where the game binds
its handler.

**Team order is a third thing, and it is not an action.** Slot 0 leads the next
battle, so the order is a real decision, but reordering does not consume the
turn. It is exposed as its own verb (`Game.reorder(a, b)`, `Bot.rearrange()`,
`POST /reorder`, `w a b` in the REPL) and advertised in the state as
`can_reorder`. Folding it into `actions` would put fifteen swap pairs next to
the moves at every map node and make the turn count mean something else.

The engine binds it to a hand-rolled pointer drag on the team bar, which lives
outside every `.screen`, which is why `__pk_choices` never saw it. We do not
simulate the drag: under all of it the drop does exactly
`[team[a], team[b]] = [team[b], team[a]]` and re-renders, and the Elite Four
prep screen has its own drag that mutates the same `state.team`. So one
primitive covers both, with no dependence on coordinates or layout.

To explore the bundle: `python3 tools/deobfuscate.py site/js/bundle.*.js`. It
works out the obfuscator's internal names by itself, since they change with every
release.

## Real pitfalls

Constraints that do not announce themselves. Worth rereading before changing
anything:

- **A label must not carry a sprite fallback.** When an image fails to load the
  engine writes a pictograph in its place, such as "🤍 Silk Scarf" for an item whose icon
  is missing from `site/`, and holes are allowed there. Whether it is present
  depends on a 404 coming back, so the same decision read two ways depending on
  timing, and differently again on a machine with different holes. That is not
  cosmetic: the linear feature sets PARSE labels, so a different label is a
  different vector, a different argmax, and from there a different run. It cost
  five of fifty benchmark rows their reproducibility. `labelFor` strips
  astral-plane pictographs; a shiny's ★ stays, because that one is engine data.
  Anything new that reads label text inherits this, so check it stays stripped.
- **A failed reset used to be silent.** Two blind 300 ms sleeps clicked into Story
  mode, and if a click did not land the caller played on, in the PREVIOUS run,
  whose badges were then filed under the new seed. `reset` now waits for a
  positive signal and then checks the invariant: a fresh run is the trainer screen
  with no badges and no team. It raises rather than returning something plausible.
- **`load_images=False` is not benchmark-safe.** Blocking images changes element
  sizes, and whether an option counts as available is decided by
  `getBoundingClientRect`, so the option list itself moves: measured, 3 of 15 runs
  differ. It is a speed knob for looking at things, never for measuring them.
- **The site does not answer 404 for missing files**: it returns `index.html` with
  status 200. Without checking magic bytes the mirror fills with HTML dressed as
  `.png`. See `SIGNATURES` in `assets/mirror.py`.
- **Keep download concurrency low.** With 24 requests in flight the site cuts us
  off and *everything* fails silently, which is worse than being slow. The mirror
  runs at 6 and repairs missing files sequentially, from the exact list the
  verification produces by playing.
- **At game over the engine wipes `state`**: empty team, no badges. The
  end-of-run summary needs `Game.last_alive`, the last snapshot taken while the
  run was alive.
- **Never declare a local with the same name as a global you mean to replace** in
  `bridge.js`: you shadow it and rewrite the wrong copy. Symptom:
  `Assignment to constant variable` that has nothing to do with `const`.
- **Two Playwright sync instances cannot live in the same thread.** One `Game` per
  thread, full stop. This is why the API tests reuse the session-wide fixture.
- **The sync API is bound to its creating thread**, so `api/server.py` is
  single-threaded by necessity: `serve_forever()` must run on the thread that owns
  the game, or you get `greenlet.error: Cannot switch to a different thread`.
- **Playwright's sync API refuses to start inside a running asyncio loop**, which
  is exactly what Jupyter keeps open. It checks `loop.is_running()` and raises
  `It looks like you are using Playwright Sync API inside the asyncio loop`, so
  `nest_asyncio` does not help. `interfaces/python/driver.py` does not fight the
  loop, it leaves it: when one is running, the game is built and driven on a
  plain thread that has none. Every call is marshalled to that one thread,
  because of the constraint above.
- **`maxTeamSize` is a high-water mark, not a limit.** The real limit is 6.
- **Non-usable items open an equip modal** which is not a `.screen`. Anything that
  only watches `.screen` elements gets stuck there forever.
- **And it is not the only one.** The engine builds two more interactive layers
  straight onto `document.body`, neither a `.screen`: `#eevee-choice-overlay`
  (`showBranchingChoice`, for Eevee, Gloom, Poliwhirl, Slowpoke and friends, a real
  2-8 way player choice) and `#egg-overlay` (`playEggReveal`, tap to continue,
  reached by buying an egg at the Poke Mart). Both are `await`ed, so they do not
  merely hide a choice, they stall the run until something clicks. Screen-id
  lists cannot fix these, see `TODO.md`. The lesson from the equip modal was
  written down once and did not generalise; assume any new interaction is NOT a
  `.screen` until checked.
- **The map is SVG**: nodes have no `.click()`.
- **Half the engine is not on `window`.** `MOVE_POOL`, `getBestMove`,
  `getMoveForPokemon`, `TYPE_CHART`, `TYPE_ITEM_MAP` are script-global lexical
  bindings: `typeof MOVE_POOL` is `"object"` but `window.MOVE_POOL` is
  `undefined`. Read them with the `g()` eval helper in `bridge.js`, or you get
  `undefined` and no error.
- **Item effects are prose, not data.** An item is `{id, name, desc, icon}` and
  nothing else; every magnitude is inline in the battle code keyed on the string
  id (`heldItem.id === 'leftovers'`). There is no stat or multiplier field to
  read. The `id` is the only stable handle, and `__pk_obs` currently drops it.
- **Clearing localStorage makes the game re-run its tutorial every time.** We
  clear it in `INIT_SCRIPT` so no saved state leaks between runs, and the price
  is that the game greets a first-time player on every run. A human clicks the
  callouts away; a bot never does, so they stack up, one per team slot, over the
  map and the battle screen alike. `HIDE_TUTORIAL_CSS` in `browser.py` hides
  them. Purely cosmetic, since they sit outside every `.screen` so they were never
  offered as actions, and actions are applied by dispatching an event on the
  element rather than clicking a coordinate, so they never intercepted anything
  either.
- **`bridge.js` is re-read from disk on every run; `browser.py` is not.**
  `BRIDGE.read_text()` sits inside `load()`, so a process that has been running
  for an hour injects whatever is on disk NOW, while `INIT_SCRIPT` is the string
  it imported when it started. `git pull` mid-run therefore pairs a new bridge
  with an old init script. **Anything bridge.js needs from `INIT_SCRIPT` must
  degrade when it is absent**. `__pk_settle` falls back to `performance.now`
  when `__pk_realNow` is missing, which is also correct: an old init script
  does not virtualise the clock, so there the real one is the right one.
  Without that degradation, every long-running training breaks on pull.
- **`INIT_SCRIPT` is substituted with `str.replace`, not `%`.** It is full of
  prose, and a comment mentioning a percentage made `INIT_SCRIPT % cfg` raise
  "not enough arguments for format string" from a line nowhere near the change.
  The scaffold's bot templates had the same problem for the same reason, since an LLM
  bot template is full of JSON, and both now use plain substitution.
- **Seeds are 32-bit.** `(cfg.seed >>> 0) || 1`, so seed 0 is seed 1 and seed
  N is seed N + 2**32. `normalise_seed` rejects anything outside the range
  rather than truncating, because above 2**53 Python's `& 0xFFFFFFFF` and JS's
  `>>> 0` disagree: there is no truncation that records the seed that ran.
- **The bundle filename carries a content hash** and changes with every game
  release. If something breaks all at once, first thing: `pokelike mirror`.
- **Not every failure should be recovered from.** The LLM bot falls back to a
  safe choice when a call fails, which is right for a timeout and wrong for a
  401: a bad token fails identically forever, so falling back on it plays the
  whole run on the backup heuristic and files it as an `llm` entry no model
  ever played. Auth and model-not-found raise `LLMConfigError` and stop the
  run.
- **A recoverable fallback is still not a decision the model made.** The other
  half of the same problem: timeouts *should* fall back, and every one of those
  turns is our backup heuristic playing under the model's name. So the harness
  counts them and `fallback_rate` is reported next to the score, flagged above
  0.1. A row that looks like a mediocre model is often a broken run.
- **`playwright install` exits 0 even when the host is missing libraries.** It
  only warns. Trusting the exit code made `setup` report success on a Raspberry
  Pi while every later command died with a stack trace, so setup now launches
  the browser to check. Never infer "it works" from an installer's exit code.
- **The engine's score formula is a Battle Tower formula.** Two of its six terms
  are dead in Story mode: `mapsCleared` is incremented in exactly one place in
  the bundle, inside `bumpEndlessCounters()`, which only runs on the endless
  path; and `winBonus` needs the whole League beaten. What is left is
  `5·KO − 10·faints`, and badges do not appear at all, which is how a run with
  three badges scores −5. Rank Story runs by **badges**, and see
  `experiments/env/rewards.py` before designing any objective on top of it.

## Scoring

The engine already knows how to compute it (`finalizeRunScore`) and how to count
(`foldBattleIntoRunStats`), but it only wires the two together in Challenge mode:
the call site reads `state.challengeId && state.runStats && fold(...)`.

Forcing `challengeId` is the obvious shortcut and it is **wrong**: that flag
changes the rules, among other things raising the Elite Four's levels
(`challengeId ? Math.max(0, 10 + challengeEliteLevelMod) : 0`). So `bridge.js`
wraps `runBattle` and hands the result to the game's own counting function:
rules untouched, native counters.

Always compare with `points_no_time`. The time bonus depends on `Date.now()`,
which we freeze for determinism, so it sits pinned near 1000 and would drown out
everything else.

## Reproducibility

The run seed is `Date.now() ^ (Math.random() * 2**32)` and everything flows from
the engine's PRNG seeded with it. `browser.py` pins **both** in a script that runs
before the bundle, caps `setTimeout` at 1 ms, and runs `performance.now()` on a
virtual clock so animations resolve at once rather than in real time, see
[Performance](#performance) for why that last one is what actually mattered.
Same seed + same actions = same run, score included.

Three clocks, three different reasons, and mixing them up breaks something
different each time:

| | what it does | why |
|---|---|---|
| `Date.now` | frozen, +16 ms a read | the run seed is drawn from it, and the score's time bonus |
| `performance.now` | virtual, +`tick` ms a read | the engine paces animations off it |
| `__pk_realNow` | the true one | `__pk_settle` has to measure a real timeout budget |

A fresh browser context per run: reusing the page would stack another init script,
and another reseed, on every reset.

## Tests

The regression net lives in `tests/golden/runs.json`: recorded runs, replayed and
compared. The fingerprint holds **only engine data** (screen ids, node types,
Pokémon names, scores) and never text we write ourselves. That is what let the whole
codebase be translated from Italian to English with proof that behaviour did not
move.

Regenerate it with `uv run python tests/record_golden.py` **only** when the game
itself has changed upstream and you have checked the new behaviour by hand.
Regenerating it to make a red test go green defeats the point.

## Performance

~3 s per run with a fast policy, a few milliseconds of that ours. Runs are
independent: to go faster, launch more processes, not more threads, and measured
on 22 cores, eight collectors is the knee, twelve buy 7%.

**Wait for the game to react; never sleep a guessed interval.** Three fixed sleeps
were once 43% of a run: 70 ms after every action for something that happens in
0.4 ms, and two 300 ms waits for a menu that appears in 17 ms. They could not
simply be shortened, because what the 70 ms really bought was that `_settle` did
not read the screen before the engine had left it and hand back a stale state.
`__pk_apply` returns a signature of the decision it acted on and
`__pk_await_change` waits for the engine to leave it, safe to poll because it
only reads, unlike `__pk_pump`.

**The virtual clock is what makes that speed, and capping timers is not
enough.** The engine paces a battle by asking what time it is and working out
how far along it should be, not by counting ticks, so capping `setTimeout`, or
routing timers and `requestAnimationFrame` through a `MessageChannel` to dodge
the browser's 4 ms clamp, each buys only 3-6% (measured). `performance.now()`
therefore jumps `tick` ms on every read (`Session.tick`, 64 by default), which
collapses an 800 ms battle animation to about 180 ms. Without it, ~79% of a
run's wall clock is `__pk_settle` waiting on the battle screen for an outcome
the engine has already decided.

`__pk_realNow` is the true clock, kept for anything that must measure real
elapsed time, such as `__pk_settle`'s own timeout budget, which on the virtual clock
would be spent in a few hundred reads. `--watch` sets `tick` to 0: a person
watching wants to see the battle.

The LLM bot is far slower (one or more HTTP calls per decision) and burns roughly
30k tokens per run.

## Submissions

`bots/` takes bots from anyone, via fork and pull request. Two rules that
are not obvious and matter:

- **A submission must be self-contained.** A trained policy freezes its state
  encoding inside the bot file rather than importing `experiments/env/encoding.py`,
  so improving the training code cannot silently change what past submissions
  mean. `bots/dyna-q/bot.py` is the worked example. The one deliberate exception
  is `pokelike.bot.llm`, above.

- **Name collisions are left to git.** `bots/` is flat, so two submissions cannot
  share a folder name and the conflict surfaces on the pull request. The
  fingerprint is deliberately NOT used as a name: it is derived from the content,
  so it would change on every retrain and take every link with it. `--author` is
  what distinguishes people in the standings.
- **Only a complete benchmark writes an entry.** `--runs N` and `--dry-run` both
  print the result and file nothing: a score over N seeds is not comparable to
  one over 50, so it is not a submission, and a `--runs 5` sanity check must
  not leave a real entry behind for the next `git add` to pick up.
- **The benchmark records the game bundle's sha256.** Scores from before and
  after an upstream game update are not comparable, and without the hash a
  leaderboard mixes them silently.

LLM entries are accepted but flagged as not independently reproducible:
providers change models behind a fixed name and sampling is stochastic.

## The frozen harnesses in llm-bench/

**`llm-bench/*/harness/bot.py` is not editable once a result exists beside it.**
Every recorded row is a claim about exactly that file; changing it makes the claim
false, and no error would ever say so. An improvement is a new directory, and the old
rows stay valid under the version where they were earned. That is why the version is
in the path and not in a variable.

They are mechanical copies of `bot/llm.py`, not imports of it, so that improving the
shared harness for `bots/` cannot silently change what a recorded score meant.

### What each version asks

| | loop | memory | tokens |
|---|---|---|---|
| `v0` | one call a turn, 4 tools, 4 rounds | last 6 moves, within the run | 1500 |
| `v1` | v0 | plus 12 notes surviving the run: `remember`/`revise`/`forget` | 1500 |
| `v2` | plus the last 3 turns carried verbatim, a `plan` tool, 6 rounds | v1's notes | 4000 |

`v0`'s prompt holds facts and no strategy on purpose: advice in a prompt measures how
well models follow OUR advice. `v2` breaks that deliberately, because measurement
forced it. Under v0's prompt two models played fifty runs each and called `remember`
zero times, and "memory does not help" and "the models never used it" are different
findings. So v0 and v2 ask genuinely different questions and their rows are never
ranked together.

### Three things to know before touching any of it

- **`pokelike.core.render` is imported, not copied**, and it is behaviour rather than
  an interface. Every pass records a sha256 of the harness *and* of the render module,
  and the table marks a row ⚠︎ when either stops matching disk. Changing `render.py`
  is allowed; it just gets caught. The fingerprint is taken when a pass STARTS, not
  when it records, so an edit mid-pass cannot yield a row certifying code it never ran.
- **`pokelike.leaderboard.Artifact` and `pokelike.bot.base.Bot` are frozen import
  paths.** All three harnesses import them, as do five submitted bots whose files are
  fingerprinted against their scores. They cannot move without a permanent shim.
- **`CROSS_RUN_MEMORY` is asked of the harness, never hardcoded.** A version carrying
  notes between runs has no independent runs, so `--workers > 1` is refused and the
  `learn` column appears. Adding a version needs no edit in `llmbench.py` or `run.sh`.

### What a run writes, and where

One directory per command, `llm-bench/<version>/logs/<stamp>/`:

| file | what it holds |
|---|---|
| `command.json` | what was asked: harness, models, seeds, workers, repeat, endpoint. **Never a credential**. `record_command` refuses a payload with a credential-shaped key |
| `<model>-passN.log` | one line per finished run, flushed as it happens. What you `tail -f` |
| `<model>-passN.jsonl` | one object per decision: the option taken, the options it had, the reason, tokens at turn/run/pass level. No prompts, since they are reconstructible from the harness plus the seed |
| `-notebook.log` | under `v1`/`v2`: the notes as they stood at the end of each run, `unchanged` when nothing moved |
| `-plan.log` | under `v2`: the route it planned for each map |

Results live **apart**, `results/<model>.json`, one file per model with every pass
appended, and that is the comparable record, and ten commands over three days build one
model's history. Only a pass over the standard fifty seeds may be recorded, compared
BY VALUE: `records()` is a function with a test because the version that compared
lengths would have recorded fifty seeds of somebody's own choosing.

Logs are gitignored. Every statistic in the table is derived from the rows at print
time, so nothing recomputable is stored, which is why cost is never written into a
result, and why regenerating the table after deleting or recording anything is on you.

One naming trap: `self.memory` is the journal-trim size, `MEMORY` moves of history.
The notes are `self.notebook`, the plan is `self.plan`, the carried exchanges are
`self.scratch`. Two harnesses have been generated mechanically from an earlier one and
both times the rename was where the bugs were.

## Secrets

LLM credentials come from `FW_ENDPOINT`, `FW_TOKEN`, `MODEL_ID`, or from the
`--endpoint`, `--api-key` and `--model` flags, which override them. `--api-key`
also takes `@path` and reads the file, because a literal key on a command line is
visible in `ps` to every user of the machine and is saved in shell history.

Never write a credential into code, comments, the README or the run registry. The
token reaches exactly one place, the `Authorization` header, and must never
appear in a result, a log or an artifact. `stats/` is gitignored.
