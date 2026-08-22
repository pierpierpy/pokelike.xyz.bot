# AGENTS.md, pokelike.xyz.bot

Notes for agents working on this repo.

**Read [README.md](README.md) first.** It is the human tour: what the project
does, how it is installed and used. This file adds what someone *changing* the
code needs, internals, pitfalls, and the reasoning behind decisions that look
odd, and the per-folder `AGENTS.md` files add the specifics of each area:

- **[bots/AGENTS.md](bots/AGENTS.md)**, the bot competition: how a folder becomes
  a bot, the fingerprint, self-containment, the LLM harness knobs and seams.
- **[experiments/AGENTS.md](experiments/AGENTS.md)**, the research area: the MDP,
  the reward registry, what is tracked and why, measuring a candidate by path.
- **[llm-bench/AGENTS.md](llm-bench/AGENTS.md)**, the model benchmark: the frozen
  harnesses, the seven-key fingerprint, what a pass writes.

The human-facing counterpart of each is the `README.md` beside it.

**Orientation**
- [What this is](#what-this-is)
- [Commands](#commands)
- [Architecture](#architecture)
- [Design overview](#design-overview)

**How it works**
- [Talking to the game](#talking-to-the-game)
- [The HTTP API](#the-http-api)
- [Scoring](#scoring)
- [Reproducibility](#reproducibility)
- [Performance](#performance)

**Before you change anything**
- [Real pitfalls](#real-pitfalls)
- [Tests](#tests)
- [The frozen harnesses](#the-frozen-harnesses)
- [Secrets](#secrets)

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
uv run pokelike play --region johto      # any of kanto, johto, hoenn, sinnoh
uv run pokelike bot run --bot mine --regions all   # all four, stopping at a loss
uv run pokelike schema           # what a bot receives, printed from a live game
uv run pokelike history -d       # what you played here, columns explained
uv run pytest                    # full suite, ~1 minute, needs the game on disk
uv run pytest -m "not slow"      # 163 tests in 6 s, no browser. What CI runs

# THE COMPETITION: your code is the entry, the game is fixed
uv run pokelike bot new mine                        # a folder that already plays
uv run pokelike bot new mine --llm                  # ... from the shared LLM harness
uv run pokelike bot run --bot random --runs 5       # play it
uv run pokelike bot run -d --runs 1                 # log every decision
uv run pokelike bot bench --bot random              # the 50 standard seeds, records
uv run pokelike bot bench --bot random --dry-run    # ... without writing an entry
uv run pokelike bot board                           # the standings, from disk

# THE MODEL BENCHMARK: the scaffold is frozen, the model is the entry
uv run pokelike model bench --harness v4 --model a/b
uv run pokelike model bench --harness v4 --model a/b --set notes=4  # smaller notebook
# --set goes to the harness constructor, which refuses by name what it does not
# know. Shared flags are the same for every version; a version's own knob is its own.
uv run pokelike model board --harness v4            # that version's table
uv run pokelike model watch                         # follow the running pass
uv run pokelike model watch --stamp 20260820-1533   # pick one, when several run
uv run pokelike model watch --all                   # every pass on this machine
# --harness is REQUIRED on both: a version is the question a row answers
# credentials: .env at the repo root, then $FW_ENDPOINT/$FW_TOKEN/$MODEL_ID, then
# --endpoint/--api-key/--model. Later always wins, and .env is the one to use:
# a key on a command line is in ps for every user and in your shell history
#
# The flat names `bench`, `leaderboard`, `llm-bench` and `new-bot` were removed,
# not aliased, and there is no implicit verb: `pokelike bot` alone is an error.

uv run python -m experiments.example.train --episodes 20     # the shape of one
uv run python -m experiments.sarsa.train --episodes 300      # the real thing
uv run pokelike bot bench --bot experiments/mine --dry-run   # measure a candidate
```

Two ports, kept distinct: the **asset server** (the game files, served to the
headless browser) defaults to **8422** (`--port`); the **HTTP JSON API**
(`pokelike api`) defaults to **8423** (`--api-port`).

## Setup on minimal Linux

`pokelike setup` downloads the browser and the offline game and checks the browser
actually launches. On minimal images (Raspberry Pi, servers, containers) Chromium's
system libraries are often missing, and `playwright install` exits 0 even when they are,
it only warns, so `setup` launches the browser to check rather than trusting the exit
code. When that is the case it prints the fix:

```bash
sudo $(which python) -m playwright install-deps chromium
```

Use `sudo $(which python)`, not plain `sudo playwright`: the virtualenv is not on root's
PATH. There is no environment to activate, `uv run` handles it; `source
.venv/bin/activate` and then dropping the `uv run` prefix works too.

## Architecture

```
site/                    the downloaded game (gitignored, ~130 MB)
src/pokelike/
├── core/                SHARED LOGIC, the only part that knows how to play
│   ├── bridge.js          injected AFTER the bundle: observes and acts. Decides
│   │                      what is in the state, and the ORDER actions come in
│   ├── init.js            injected BEFORE the bundle: seeded Math.random, pinned
│   │                      clock, capped timers. This is what makes a seed replay
│   ├── browser.py         Playwright headless: launches, injects both, filters
│   ├── game.py            class Game: reset/state/step/score/reorder
│   ├── render/            state to text. The SAME package prints your terminal
│   │                      and feeds an LLMBot by default: team, world (the map),
│   │                      actions, screen (the whole view)
│   ├── runner.py          play_run(): the one loop that plays a run with a bot
│   └── schema/            what a bot receives: fields (the reference) and
│                          describe (generated from a LIVE state, and
│                          self-checking: a field in a real obs but missing from
│                          FIELDS is reported as undocumented)
├── bot/                 WHAT RUNS A BOT, not the bots themselves
│   ├── base.py            abstract Bot: only act() is required
│   ├── catalogue.py       finds and loads a bot from its folder in bots/
│   ├── llm/               the harness every llm-* bot shares: agent (the class
│   │                      and the turn), loop (the agentic rounds), tools,
│   │                      transport (HTTP and retries), journal (what it
│   │                      remembers), prompt, fallback, config, record.
│   │                      Shared so a benchmark of models holds it still
│   └── random_bot.py      the baseline. Here rather than only in bots/random/
│                          because compare() defaults to it, so it has to work
│                          in a checkout with no bots/ at all
├── assets/
│   ├── mirror/            builds site/ in five phases: phases, fetch,
│   │                      signatures (the magic-byte check), build
│   └── server.py          serves site/ from disk
├── logging/             WHAT A MEASURED RUN WRITES DOWN, and the one thing
│                        `arena/` and `harness/` both need: passlog (the table,
│                        the decision trace, the runs file, the notebook and the
│                        plan), heartbeat (how liveness is known), trace (the
│                        per-decision enrichment). Here rather than inside either
│                        one, because putting it in either would make the bot
│                        competition depend on the model benchmark or the reverse
├── stats/registry.py    SQLite in stats/runs.db
├── arena/               THE BOT COMPETITION: your code is the entry
│   ├── bench/             the standard 50-seed benchmark: seeds, run, progress,
│   │                      report
│   ├── scaffold.py        bot new: writes a bot folder that already plays
│   └── leaderboard/       reads bots/*/result.json, ranks, fingerprints:
│                          artifact, record, table. Defines Artifact, imported by
│                          the frozen harnesses and the bots as
│                          pokelike.arena.leaderboard.Artifact, a frozen import
│                          path their fingerprints cover
├── harness/             THE MODEL BENCHMARK: the scaffold is frozen
│   ├── llmbench/          versions (and the fingerprint), command (one command's
│   │                      directory), passlog + heartbeat (what a pass writes and
│   │                      how liveness is known), passes and parallel + worker
│   │                      (running them), results, tables, pricing
│   └── watch/             `pokelike model watch`: read (a trace into records),
│                          discover (which passes exist and which are live),
│                          liveness, dashboard (one pass), overview (all of them)
└── interfaces/          how something outside drives the game
    ├── cli/               a human, in a terminal: main (the parser only), help
    │                      (the boxed screens), shared (flags and helpers), and
    │                      commands/ one module per family
    ├── api/server.py      a program, over HTTP
    └── python/            a script, a notebook or the REPL
        ├── driver/          session(), open_game(), play(), compare()
        └── example.ipynb    the cell-by-cell walkthrough
llm-bench/               a MODEL benchmark, not a bot one: the harness is frozen
│                        and the model is the only thing that varies. See
│                        llm-bench/AGENTS.md
├── docker/                the container long runs happen in. Build context is
│                          the REPO ROOT, and .dockerignore must stay there
├── v0, v2, v4/harness/    FOUR FROZEN FILES each, never edited once a result
│                          exists beside them: bot.py, render.py, bridge.js, init.js
└── v*/logs/<stamp>/       ONE DIRECTORY PER COMMAND: command.json, plus a .log
                           and a .jsonl of decisions per pass. Results stay one
                           file per model, outside, because that is the record
experiments/             research. OURS are tracked as worked examples; anything
│                        else anyone creates here is gitignored by default. See
│                        experiments/AGENTS.md
├── env/                   the game as an RL problem: environment, rewards, encoding
├── example/               the smallest complete experiment
├── dyna-q/                tabular RL. LOST to random, and kept for that
├── sarsa/                 linear function approximation. The one that worked
└── llm/                   prompt strategies compared on identical seeds
bots/                    THE BOTS. One folder each: bot.py, artifacts/,
│                        result.json. Nothing registers them. See bots/AGENTS.md
tests/                   golden fingerprints + unit tests
utils/deobfuscate.py     makes the bundle readable (needs node)
```

Nothing in `src/` may import from `experiments/`: it is a scratch area, mostly
untracked, and the package cannot depend on files that are not in the clone.

`interfaces/` and `bot/` contain no game logic: they all go through `Game`'s five
methods. If you feel like putting a game rule in the CLI, it belongs in `core`.

Decision logging lives in `runner.play_run` so that a log means the same thing
whatever is playing; bots add at most one line through the optional `reason()`
hook. `bot/` is deliberately not under `interfaces/`: the interfaces are entry
points (something outside drives the game through them), a bot is an extension
point (you write one, and the interfaces run it).

## Design overview

The shape of the whole thing, from the game up to a bot. (A fuller, discursive
version of this lives in the maintainer's private `ARCHITECTURE.md`; this is the
summary that belongs in the repo.)

**Three subjects, not one: the game, the shared loop, the bot.** Most confusion
about `config.state_view` and `render.screen()` comes from forgetting that those two
live inside the *bot*, not in the game. The loop is `runner.play_run()`, and it is
the same for the random bot, a SARSA and a 400-billion-parameter LLM:

- The game never talks to the bot. The loop reads the state and hands it over.
- The `trace` is recorded by the loop, identically for everyone, which is why
  `reason()` exists: it is the one place a bot adds what only it knows.
- A bot returns an **index**, not an action. Out of range, and the move fails.

**The state is a hand-written projection, not everything the game knows.** `obs`
is a dict with seven keys (`team`, `bag`, `map`, `run`, `actions`, `steps`,
`screen`). It is one turn's snapshot, so keys that only exist on other screens are
absent, and, crucially, it lists only the fields `bridge.js` was written to
expose. Nothing in Python can invent a field the bridge never read. See
`uv run pokelike schema` for the live reference (generated from a real
observation, so it cannot describe a game that no longer exists).

**`render` is a package of pure functions, with two consumers.** `core/render/`
is not a class and holds no state: eleven functions that take part of a state and
return a string. It is both what `pokelike play` prints and the default view an
`LLMBot` sends to the model. It renders what a person would look at rather than
everything true, and deliberately throws a lot away (the type→item table, the map
edges, raw base stats, most node ids).

**A bot has two levels, and they are different jobs, not degrees of the same one.**
Inherit from `Bot` and *you* decide the move (you write the rule). Inherit from
`LLMBot` and the *model* decides; your job is what it sees and can do. Overriding
`act` on an `LLMBot` throws away the agentic loop that was the reason to inherit
from it, nobody does, and five of the six `llm-*` bots define no method at all.

**One model call decides the whole turn.** The loop calls `reorder` before `act`,
so `LLMBot` makes its single HTTP call inside `reorder`, caches the answer keyed by
`steps`, and `act` returns it without asking again; a `set_lead` tool call is
recorded there and applied by the loop, not by the bot. Three exceptions are told apart
on purpose: an auth/config error or a spent token budget kills the run rather than
quietly finishing it on the backup heuristic, while a transient failure falls back to a
safe move and is counted into `fallback_rate`. Detail in [bots/AGENTS.md](bots/AGENTS.md).

**The LLM harness is copied into each benchmark version on purpose.** The shared
`bot/llm/` *must* be free to improve, because `bots/` reads it. A benchmark wants
the opposite: if a frozen harness imported the shared library, the next improvement
for a submission would silently change what every recorded score meant. So
`llm-bench/<v>/harness/bot.py` inherits from `Bot`, not `LLMBot`, those are
independent, parallel implementations that merely resemble each other because the
second was born from the first. Detail in [llm-bench/AGENTS.md](llm-bench/AGENTS.md).

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

`bridge.js` is injected after the bundle and exposes a small surface on `window`:
`__pk_layer()` (which screen or modal is active), `__pk_choices()` (the legal
actions, in a stable order), `__pk_apply(c)` (perform one), `__pk_obs()` (the
whole state as JSON), and `__pk_settle(ms)` (run the engine's own transitions
forward between decisions). Half the engine is not on `window`, `MOVE_POOL`,
`getBestMove`, `TYPE_CHART`, `TYPE_ITEM_MAP` are script-global lexical bindings,
so the bridge reads them with a one-line `g = (n) => { try { return eval(n) } ... }`
helper. No pixels are looked at; screenshots exist (`Game.screenshot`) but are for
humans only.

Actions come in two kinds: map moves go through `onNodeClick(node)` (a direct
call), other choices activate a DOM element because that is where the game binds
its handler.

**Team order is a third thing, and it is not an action.** Slot 0 leads the next
battle, so the order is a real decision, but reordering does not consume the
turn. It is exposed as its own verb (`Game.reorder(a, b)`, `Bot.reorder()`,
`POST /reorder`, `w a b` in the REPL) and advertised in the state as
`can_reorder`. Folding it into `actions` would put fifteen swap pairs next to
the moves at every map node and make the turn count mean something else. The
engine binds it to a hand-rolled pointer drag on the team bar, outside every
`.screen`; we do not simulate the drag, under all of it the drop is just
`[team[a], team[b]] = [team[b], team[a]]` and a re-render, and one primitive
covers both the team bar and the Elite Four prep screen.

To explore the bundle: `python3 utils/deobfuscate.py site/js/bundle.*.js`. It
works out the obfuscator's internal names by itself, since they change with every
release.

## The HTTP API

`pokelike api` (default port **8423**) exposes the five `Game` methods as JSON over
`http.server`. It is **single-threaded by necessity**: Playwright's sync API is bound to
the thread that created it, so `serve_forever()` must run on the thread that owns the
game. The browser stays alive between calls.

| Method | Route | What it does |
|---|---|---|
| `POST` | `/new` `{"seed":42}` | start a run |
| `GET` | `/state` | full state + a ready-to-print `view` field |
| `GET` | `/actions` | just the legal actions |
| `POST` | `/action` `{"index":1}` | take it → new state (409 if illegal) |
| `POST` | `/reorder` `{"a":0,"b":2}` | swap two team slots, free |
| `GET` | `/score` | score using the game's own formula |
| `GET` | `/screenshot` | a PNG of the current screen |
| `GET` | `/schema` | what the state contains, described from itself |

An illegal move returns 409 (`IllegalAction`); a malformed body, 400; an unknown route,
404. The asset server that feeds the headless browser is a separate process on port
**8422** (`--port`); the two are kept distinct.

## The four regions

The game has four story regions (Kanto, Johto, Hoenn, Sinnoh), each a WHOLE GAME: its own
eight gyms, its own starters, its own Elite Four, and a badge count that restarts. Nothing
carries between them, so a campaign is a SEQUENCE of runs and the only thing that crosses
is the bot.

**Every region but Kanto is locked until you have won one**, and the game decides that
from the Hall of Fame in `localStorage`:

    locked(gen 2)    = !hasStoryWin(1)
    locked(gen 3, 4) = !hasAnyStoryWin()
    hasStoryWin(g)   = getHallOfFame().some(r => !r.endless && hofEntryGen(r) === g)

`init.js` clears `localStorage` on every load so no saved state leaks between runs, which
also means we have never won anything. `Game.reset` therefore writes the entry back FROM
PYTHON after the load, and only when a region other than Kanto is asked for. That is not
squeamishness about editing a file: every frozen harness carries its own `init.js` and a
recorded result hashes it, so this is the only way to let v0-v5 play a second region
without touching them.

`normalise_region` refuses what does not exist rather than falling back to Kanto, for the
same reason the seed is checked before a run starts: a typo would otherwise file a Johto
row that never was.

`runner.play_campaign()` plays the regions in order and stops at the first not won. What a
bot keeps across a boundary is `LLMConfig.keep_across_regions`, default `("notes",)`, and
the four seams around it are on `Bot` so a policy answers them too:

| seam | when |
|---|---|
| `region_cleared(done) -> str \| None` | the region ended, memory STILL INTACT, so a bot can have its own model summarise |
| `region_opening(text)` | the other side, after the forgetting |
| `reset_memory(keep=...)` | the forgetting itself, done by the runner |
| `memory_text()`, `memory_messages()` | the material, so nothing has to reach for privates |

`memory_messages()` can only return what was KEPT: `scratch_turns` is a retention policy,
not a read filter, so a summary that wants the whole region wants `memory=-1` instead, one
line per turn.

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

**The engine's score formula is a Battle Tower formula.** Two of its six terms
are dead in Story mode: `mapsCleared` is incremented in exactly one place in the
bundle, inside `bumpEndlessCounters()`, which only runs on the endless path; and
`winBonus` needs the whole League beaten. What is left is `5·KO − 10·faints`, and
badges do not appear at all, which is how a run with three badges scores −5. Rank
Story runs by **badges**, and see `experiments/env/rewards.py` before designing
any objective on top of it.

## Reproducibility

The run seed is `Date.now() ^ (Math.random() * 2**32)` and everything flows from
the engine's PRNG seeded with it. `core/init.js` pins **both**, runs before the
bundle, caps `setTimeout` at 1 ms, and runs `performance.now()` on a virtual clock
so animations resolve at once rather than in real time (see
[Performance](#performance) for why that last one is what actually mattered).
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
the engine has already decided. `--watch` sets `tick` to 0: a person watching
wants to see the battle.

The LLM bot is far slower (one or more HTTP calls per decision) and burns roughly
30k tokens per run.

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
  astral-plane pictographs (the `PICTOGRAPH` regex); a shiny's ★ stays, because
  that one is engine data. Anything new that reads label text inherits this.
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
  `.png`. See `SIGNATURES` in `assets/mirror/signatures.py`.
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
  is exactly what Jupyter keeps open. `nest_asyncio` does not help.
  `interfaces/python/driver/` does not fight the loop, it leaves it: when one is
  running, the game is built and driven on a plain thread that has none, and every
  call is marshalled to that one thread.
- **`maxTeamSize` is a high-water mark, not a limit.** The real limit is 6.
- **Non-usable items open an equip modal** which is not a `.screen`. Anything that
  only watches `.screen` elements gets stuck there forever.
- **And it is not the only one.** The engine builds two more interactive layers
  straight onto `document.body`, neither a `.screen`: `#eevee-choice-overlay`
  (`showBranchingChoice`, a real 2-8 way player choice) and `#egg-overlay`
  (`playEggReveal`, tap to continue). Both are `await`ed, so they stall the run
  until something clicks. Assume any new interaction is NOT a `.screen` until
  checked.
- **The map is SVG**: nodes have no `.click()`.
- **Half the engine is not on `window`.** `MOVE_POOL`, `getBestMove`,
  `getMoveForPokemon`, `TYPE_CHART`, `TYPE_ITEM_MAP` are script-global lexical
  bindings: `typeof MOVE_POOL` is `"object"` but `window.MOVE_POOL` is
  `undefined`. Read them with the `g()` eval helper in `bridge.js`.
- **Item effects are prose, not data.** An item is `{id, name, desc, icon}` and
  nothing else; every magnitude is inline in the battle code keyed on the string
  id (`heldItem.id === 'leftovers'`). The `id` is the only stable handle.
- **Clearing localStorage makes the game re-run its tutorial every time.** We
  clear it in `init.js` so no saved state leaks between runs, and the price is the
  game greets a first-time player on every run. Those callouts sit outside every
  `.screen`, so they were never offered as actions; `HIDE_TUTORIAL_CSS` in
  `browser.py` hides them, including the `#tutorial-overlay` LAYER, not just
  `.tutorial-callout`, leaving the layer visible stalled every step for 90 s.
- **Both JavaScript files are re-read from disk on every run.** `_init_js()` and
  `_bridge_js()` are called inside `load()`, so a process running for an hour
  injects whatever is on disk NOW. A `git pull` mid-run swaps both under a training
  still going, and a mismatched pair is a real state: **anything `bridge.js` needs
  from `init.js` must degrade when it is absent.** `__pk_settle` falls back to
  `performance.now` when `__pk_realNow` is missing, which is also the right answer.
- **`init.js` is substituted with `str.replace`, not `%`.** It is full of prose,
  and a comment mentioning a percentage made `INIT_SCRIPT % cfg` raise "not enough
  arguments for format string". The scaffold's bot templates had the same problem
  (LLM templates are full of JSON braces), and both now use plain substitution.
- **Seeds are 32-bit.** `init.js` does `(cfg.seed >>> 0) || 1`, so seed 0 is seed
  1 and seed N is seed N + 2**32. `normalise_seed` rejects anything outside the
  range rather than truncating, because above 2**53 Python's `& 0xFFFFFFFF` and
  JS's `>>> 0` disagree.
- **The bundle filename carries a content hash** and changes with every game
  release. If something breaks all at once, first thing: `pokelike mirror`.
- **Not every failure should be recovered from.** The LLM bot falls back to a safe
  choice when a call fails, which is right for a timeout and wrong for a 401: a bad
  token fails identically forever, so falling back on it plays the whole run on the
  backup heuristic and files it as an `llm` entry no model ever played. Auth and
  model-not-found raise `LLMConfigError` and stop the run.
- **A recoverable fallback is still not a decision the model made.** Timeouts
  *should* fall back, and every one of those turns is our backup heuristic playing
  under the model's name. So the harness counts them and `fallback_rate` is
  reported next to the score, flagged above 0.1.
- **`playwright install` exits 0 even when the host is missing libraries.** It only
  warns. `setup` now launches the browser to check. Never infer "it works" from an
  installer's exit code.

## Tests

The regression net lives in `tests/golden/runs.json`: recorded runs, replayed and
compared. The fingerprint holds **only engine data** (screen ids, node types,
Pokémon names, scores) and never text we write ourselves. That is what let the whole
codebase be translated from Italian to English with proof that behaviour did not
move.

Regenerate it with `uv run python tests/record_golden.py` **only** when the game
itself has changed upstream and you have checked the new behaviour by hand.
Regenerating it to make a red test go green defeats the point.

## The frozen harnesses

`llm-bench/*/harness/` is a benchmark of *models*, and every recorded row is a
claim about the exact files that played it. Nothing there is editable once a result
exists beside it; an improvement is a new directory, not an edit. The full account,
the seven-key fingerprint, what each version asks, what a pass writes, and why
`bridge.js` and `init.js` are more dangerous than the renderer, is in
[llm-bench/AGENTS.md](llm-bench/AGENTS.md). The one rule to carry everywhere else:
**`bot/llm/`, `core/render/`, `core/bridge.js` and `core/init.js` are the
living copies that `bots/` and the CLI use; the frozen harness copies are
independent and must never import them.**

## Secrets

LLM credentials come from three places, and the later one always wins: a `.env`
file at the repository root, the environment (`FW_ENDPOINT`, `FW_TOKEN`,
`MODEL_ID`), then the `--endpoint`, `--api-key` and `--model` flags.

**`.env` is the one to use.** It is gitignored, the container already reads it
(compose `env_file:`), and since the CLI loads it too (`cli/shared.load_dotenv`,
called once in `main()` with `setdefault`, so it never overrides an export) a local
run needs no flags at all. A literal key on a command line is visible in `ps` to
every user of the machine and is saved in shell history, which is why `--api-key`
also takes `@path` and reads the file.

Never write a credential into code, comments, the README or the run registry. The
token reaches exactly one place, the `Authorization` header, and must never
appear in a result, a log or an artifact. `stats/` is gitignored, and
`record_command` refuses to write a payload with a credential-shaped key.
