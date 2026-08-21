<div align="center">

# ◓ POKELIKE.XYZ.BOT

**A headless, reproducible copy of a browser Pokémon roguelike, for the bots people
write, and for benchmarking the models that play it.**

[![Tests](https://github.com/pierpierpy/pokelike.xyz.bot/actions/workflows/tests.yml/badge.svg)](https://github.com/pierpierpy/pokelike.xyz.bot/actions/workflows/tests.yml)
&nbsp;![Python](https://img.shields.io/badge/python-3.10%2B-blue)
&nbsp;![uv](https://img.shields.io/badge/managed%20with-uv-de5fe9)
&nbsp;[![Release](https://img.shields.io/github/v/release/pierpierpy/pokelike.xyz.bot?label=release&color=de5fe9)](https://github.com/pierpierpy/pokelike.xyz.bot/releases/latest)

</div>

[pokelike.xyz](https://pokelike.xyz/) is a Pokémon roguelike that runs entirely in the
browser: pick a starter, walk a branching map of battles, catches, shops and gyms,
earn badges, and lose the run for good if your team faints. The battles play
themselves, what a player decides is the roguelike part: where to go, who to catch,
which item to hold, who leads the next fight. This repo lets you play it headless, no
window, no account, no internet, from the command line, from Python, or over an HTTP API.

![A trained policy playing a run](img/reinforcement_learning.gif)

*A trained reinforcement-learning policy, mid-run. it decided to use squirtle over and over again apparently.. lol* 

This repo is 3 things in one, use it as you please. It is: 

- an **[Environment](#1-environment)**, a headless, reproducible copy of the game you can
  simulate runs against, drive from a script or a notebook, and hand to a coding agent.
- a **[LLM agentic benchmark](#2-llm-agentic-benchmark)**, an agentic harness that runs on
  the same fifty seeds for every LLM, the output score tells the agentic/planning capabilities of a model 
- a **[Bot framework/competition](#3-bot-competition)**, you write a bot and your goal is
  to beat the game. The bot can be anything, a trained policy, a prompt, a
  rulebook, tree search, anything that turns a state into a move.

---

**Contents**

- [Environment](#1-environment)
- [LLM agentic benchmark](#2-llm-agentic-benchmark)
- [Bot competition](#3-bot-competition)
- [Install](#install)
- [Commands](#commands)
- [Documentation](#documentation)
- [Getting help](#getting-help)
- [Maintainers & contributing](#maintainers--contributing)

---

## 1. Environment

**The game lives entirely in the browser, and it has no server.** All its logic sits in
one JavaScript file, already on your machine after setup. There is no remote API to
call, we run the game in headless Chromium and talk straight to its own functions.

**"Headless" does not mean "no graphics".** It means no window. The browser still
builds the state, the buttons and the map in memory; it simply never paints them. So we
look at no pixels, the ASCII map you see is redrawn from the nodes and edges read out
of the game's memory.

The pieces, and how a decision flows through them:

```
site/                the downloaded game (not in git)
   │
assets/server.py     serves it from disk, never touching the internet
   │
headless browser     runs the game
   │
core/bridge.js       reads the state, performs the choices
   │
core/game.py         class Game  ← THE LOGIC, one copy of it
   │
   ├─── interfaces/cli/   the terminal
   ├─── interfaces/api/   HTTP JSON
   └─── bot/              whoever decides the moves
```

`Game` has five methods, and everything else goes through them:

```python
g.reset(seed=42)   # start
g.state()          # team, map, legal actions
g.step(1)          # take move 1 -> new state
g.reorder(0, 2)    # swap two team slots; free, does not use the turn
g.score()          # what the run is worth
```

You reach those five methods through three interfaces:

- **CLI**, to play or watch in the terminal. `uv run pokelike play --seed 42` drops you
  into a run; add `--watch` for a real window, or `--shots DIR` to save a PNG of every
  screen.
- **Python**, for scripts and notebooks. Open a game with `session()`, then call
  `reset`, `step` and `score`; the server and the browser are started for you.
- **HTTP API**, for any other language. `uv run pokelike api` serves the same five
  methods as JSON and keeps the browser alive between calls.

Reading a run in the terminal: the map goes top to bottom, `[here]` is where you are,
`<like this>` are the legal moves, and picking one node closes the others on that layer
forever.

## 2. LLM agentic benchmark

**How well does a language model play the game?** [`llm-bench/`](llm-bench/README.md)
answers that, and it is built so the answer is about the model and nothing else.

Every model runs inside the **same frozen scaffold**, the same prompt, the same tools,
the same rendering of the state, the same seeded clock, and plays the **same fifty
seeds**. The scaffold is copied and hashed into every recorded result, so it cannot
quietly move between one model and the next. Change it and you have a new benchmark
version, not a corrected old one; the old rows stay valid under the version that earned
them.

That makes it an unusual agentic task: no browsing, no tickets, no code, but
irreversible choices, permanent losses, and a state that barely fits on a screen.

```bash
uv run pokelike model bench --harness v0 --model qwen/qwen3.7-flash \
  --endpoint https://openrouter.ai/api --api-key sk-or-...
```

That plays fifty games, records the result, and prints a row, half an hour or so. The
standings, the versions and how to read the table are in
[llm-bench/README.md](llm-bench/README.md).

## 3. Bot competition

> **The competition is open.** Write something that plays
> [pokelike.xyz](https://pokelike.xyz/) better than mine, put it in [bots/](bots/README.md), and
> open a pull request. Anyone can enter, no permission needed.

**What counts as a bot is deliberately wide open.** A prompt around an LLM, a model
fine-tuned on the game, reinforcement learning of any flavour, a hand-written rulebook,
search over the game tree since the engine ships a battle simulator you can call. If it
picks a move given the state, it qualifies.

**How it is judged.** Every entry plays the same 50 fixed seeds, so nobody wins on luck,
and is ranked by **badges**, the game's own progress counter. One command builds your
submission, and it records the hash of the game bundle that was played, because scores
from before and after a game update are not comparable. The standings are generated from
what is measured on disk, so they cannot fall out of date.

Letting a bot play is one command, every bot ships with its weights, so there is
nothing to download or train:

```bash
uv run pokelike bot run --bot sarsa-v2 --runs 5           # play the leader
uv run pokelike bot run --bot sarsa-v2 --runs 1 -g -dd    # + the map and every value it weighed
uv run pokelike bot run --bot random  --runs 1 -d         # the baseline, one line per decision
uv run pokelike history                                   # how it went
```

![An LLM playing a run](img/llm_playthrough.gif)

*An LLM playing a run. Each turn it reads the state, may call a read-only tool, and
commits to one move with a reason, the same reasoning the `-d` flags stream in the
terminal.*

![The map, and where the bot is on it](img/llm_battle.gif)

*`-g` draws the map beside each decision: where you are, where you may still go, and
where you have already been.*

Writing one is a folder and a single method, `act(state) -> int`.
**[CONTRIBUTING.md](CONTRIBUTING.md) is the full guide**, a six-step walk-through from a
clone to a pull request, plus everything you are allowed to change. The standings, the
bar to beat, and every shipped bot are in [bots/](bots/README.md). Random is on the board
too, and the gap between flailing and the best trained policy is smaller than you would
expect.

---

## Install

You need [uv](https://docs.astral.sh/uv/) and nothing else:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```bash
git clone https://github.com/pierpierpy/pokelike.xyz.bot
cd pokelike.xyz.bot
uv sync              # creates the environment and installs dependencies
uv run pokelike setup
```

`setup` does three things, once: downloads the headless browser (~120 MB), checks it
actually starts, and downloads the game into `site/` (~130 MB, a few minutes). After
that **you never need the internet again**.

> On a minimal Linux box (Raspberry Pi, server, container) you may also need Chromium's
> system libraries: `sudo $(which python) -m playwright install-deps chromium`.

## Commands

Three families. **General** drives the game, **bot** is the competition, **model** is
the benchmark.

### General

| command | what it does |
|---|---|
| `setup` | browser + offline copy of the game. Run once |
| `mirror` | rebuild the offline copy after a game update (`--phase verify` to just check it) |
| `play` | interactive run in the terminal (`--seed`, `--watch`, `--shots`) |
| `api` | HTTP JSON server (port 8423) |
| `schema` | what a bot receives, printed from a live game |
| `history` | the runs on this machine (`-d` explains the columns, `--recent N`) |

```bash
uv run pokelike play --seed 42
uv run pokelike schema
uv run pokelike history -d
```

### Bot: the competition

| command | what it does |
|---|---|
| `bot new` | creates `bots/<name>/`, ready to play (`--llm` for a prompt bot) |
| `bot run` | plays a bot (`--bot`, `--runs`, `--seed`, `-d` to log decisions, `-g` for the map) |
| `bot bench` | the 50 standard seeds, records the result (`--dry-run` to record nothing) |
| `bot board` | rebuild the standings from what is measured on disk |

```bash
uv run pokelike bot new mine
uv run pokelike bot run --bot mine --runs 5 -d
uv run pokelike bot bench --bot mine --dry-run
uv run pokelike bot board
```

### Model: the benchmark

| command | what it does |
|---|---|
| `model bench` | a model against one frozen harness (`--harness`, `--models`, `--repeat`, `--workers`) |
| `model board` | the table for that harness (`--harness`) |
| `model watch` | follow a running pass: runs, team, map, tools, notes (`--all` for every pass) |

```bash
uv run pokelike model bench --harness v0 --model qwen/qwen3.7-flash
uv run pokelike model board --harness v0
uv run pokelike model watch --all
# credentials: $FW_ENDPOINT/$FW_TOKEN, or --endpoint/--api-key (--api-key @path reads a file)
```

## Documentation

- **[CONTRIBUTING.md](CONTRIBUTING.md)**, write and submit a bot (six steps), and how
  to change the shared library or propose a benchmark harness.
- **[bots/README.md](bots/README.md)**, the standings, and how to play any shipped bot.
- **[experiments/README.md](experiments/README.md)**, the research area behind the
  bots: training, sweeps, and what was already tried.
- **[llm-bench/README.md](llm-bench/README.md)**, the model benchmark: the harnesses,
  the standings, and how to read the table.
- **[example.ipynb](src/pokelike/interfaces/python/example.ipynb)**, drive the game
  from a notebook, cell by cell.

## Getting help

Open an issue on the [tracker](https://github.com/pierpierpy/pokelike.xyz.bot/issues), a
bug in the shared code is the most useful thing you can report. Include a seed and a step
if you have one: `uv run pokelike bot run --bot random --runs 1 -d` prints every decision
with the screen it was made on.

## Maintainers & contributing

Maintained by [@pierpierpy](https://github.com/pierpierpy). The bot competition is open
to anyone, fork, add a folder under `bots/`, and open a pull request; a submission needs
no permission and touches only your own folder. The full guide, and the rules for
changing the shared library or the benchmark, are in [CONTRIBUTING.md](CONTRIBUTING.md).

The game is somebody else's fan project; with the local copy, traffic to them is zero
after the one-time download.
