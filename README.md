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
browser: pick a starter, walk a branching map of battles, catches, shops and gyms, earn
badges, and lose the run for good if your team faints. The battles play themselves.
What a player decides is the roguelike part: where to go, who to catch, which item to
hold, who leads the next fight. This repo lets you play it headless, no window, no
account, no internet, from the command line, from Python, or over an HTTP API.

<p align="center">
  <img src="img/reinforcement_learning.gif" alt="A trained policy playing a run"><br>
  <sub><i>A trained RL policy mid-run: it just keeps sending Squirtle in, apparently. lol</i></sub>
</p>

This repo is three things in one, and you can use it for any of them:

- &nbsp;**[Environment](#1-environment)**: the core piece. A headless, reproducible copy
  of the game that you can simulate runs against, drive from a script or a notebook, and
  hand to a coding agent.
- &nbsp;**[LLM agentic benchmark](#2-llm-agentic-benchmark)**: an agentic harness that
  runs the same fifty seeds against every LLM. The resulting score measures a model's
  agentic and planning capability.
- &nbsp;**[Bot framework and competition](#3-bot-competition)**: you write a bot, and
  the goal is to beat the game. A bot can be anything that turns a state into a move: a
  trained policy, a prompt, a rulebook, a tree search. To see one think, watch
  [a bot play one decision at a time](bots/llm-example2/step.ipynb).

---

## 1. Environment

The game lives entirely in the browser and has no server. All of its logic sits in one
JavaScript file, already on your machine once you have run setup. There is no remote API
to call: this project runs the game in headless Chromium and talks straight to its own
functions.

Headless does not mean there are no graphics. It means there is no window. The browser
still builds the game's state, buttons, and map, entirely in memory, it just never draws
them on screen. As a result, no pixels are produced. The ASCII map shown in the terminal
is redrawn directly from the nodes and edges stored in the game's memory.

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

The `Game` class has five methods, and everything else goes through them:

```python
g.reset(seed=42)   # start
g.state()          # team, map, legal actions
g.step(1)          # take move 1 -> new state
g.reorder(0, 2)    # swap two team slots; free, does not use the turn
g.score()          # what the run is worth
```

You reach those five methods through three interfaces:

- **CLI**: for playing or watching in the terminal. Running `uv run pokelike play
  --seed 42` drops you into a run; add `--watch` for a real window, or `--shots DIR` to
  save a PNG of every screen.
- **Python**: for scripts and notebooks. Open a game with `session()`, then call
  `reset`, `step`, and `score`; the driver starts the server and the browser for you.
- **HTTP API**: for any other language. Running `uv run pokelike api` serves the same
  five methods as JSON and keeps the browser alive between calls.

Reading a run in the terminal: the map goes top to bottom, `[here]` is where you are,
`<like this>` are the legal moves, and picking one node closes the others on that layer
forever.

## 2. LLM agentic benchmark

How well does a language model play the game? The
[`llm-bench/`](llm-bench/README.md) benchmark answers that question, built so the
answer is about the model and nothing else.

Every model runs inside the same frozen harness: the same prompt, the same tools, the
same rendering of the state, the same seeded clock, playing the same fifty seeds. The
harness is copied and hashed into every recorded result, so it cannot quietly move
between one model and the next. Changing it produces a new benchmark version, not a
corrected old one; the old rows stay valid under the version that earned them.

That makes it an unusual agentic task: no browsing, no tickets, no code, but
irreversible choices, permanent losses, and a state that barely fits on a screen.

```bash
uv run pokelike model bench --harness v0 --model qwen/qwen3.7-flash \
  --endpoint https://openrouter.ai/api --api-key sk-or-...
```

Running that command plays fifty games, records the result, and prints a row. It takes
about half an hour. The standings, the version history, and how to read the table live
in [llm-bench/README.md](llm-bench/README.md).

## 3. Bot competition

> The competition is open. Write something that plays
> [pokelike.xyz](https://pokelike.xyz/) better than mine, add it under
> [bots/](bots/README.md), and open a pull request. Anyone can enter; no permission
> needed.

What counts as a bot is wide open. A prompt around an LLM, a model fine-tuned on the
game, reinforcement learning of any flavour, a hand-written rulebook, or a search over
the game tree, since the engine ships a battle simulator you can call. If it picks a
move given the state, it qualifies.

Every entry is judged by playing the same 50 fixed seeds, so nobody wins on luck, and
ranked by badges, the game's own progress counter. One command builds your submission,
and it records the hash of the game bundle that was played, because scores from before
and after a game update are not comparable. The standings are generated from what is
measured on disk, so they cannot fall out of date.

Letting a bot play takes one command. Every bot ships with its own weights, so there is
nothing to download or train:

```bash
uv run pokelike bot run --bot sarsa-v2 --runs 5           # play the leader
uv run pokelike bot run --bot sarsa-v2 --runs 1 -g -dd    # + the map and every value it weighed
uv run pokelike bot run --bot random  --runs 1 -d         # the baseline, one line per decision
uv run pokelike history                                   # how it went
```

<p align="center">
  <img src="img/llm_battle.gif" alt="A bot playing a run"><br>
  <sub><i>a bot playing, no window: the map is redrawn from the game's own memory</i></sub>
</p>

Writing one comes down to a folder and a single method: `act(state) -> int`.
[CONTRIBUTING.md](CONTRIBUTING.md) is the full guide: a six-step walk-through from a
clone to a pull request, plus everything you are allowed to change. The standings, the
bar to beat, and every shipped bot are in [bots/](bots/README.md). Random is on the
board too, and the gap between flailing and the best trained policy is smaller than you
would expect.

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

Run the `setup` command once. It downloads the headless browser (about 120 MB), checks
that the browser actually starts, and downloads the game into `site/` (about 130 MB,
which takes a few minutes). After that, the tool works fully offline: you will not need
an internet connection again.

> On a minimal Linux box (Raspberry Pi, server, container) you may also need Chromium's
> system libraries: `sudo $(which python) -m playwright install-deps chromium`.

## Quickstart

A few commands to get moving right away:

```bash
uv run pokelike play --seed 42                       # play a run yourself, in the terminal
uv run pokelike bot run --bot sarsa-v2 --runs 5 -d    # watch the leading bot play, decision by decision
uv run pokelike bot new mine                          # start your own bot
uv run pokelike bot bench --bot mine --dry-run        # measure it on the 50 standard seeds, records nothing
uv run pokelike model bench --harness v0 --model qwen/qwen3.7-flash   # benchmark a model instead
```

Credentials for anything that calls a model come from a `.env` file at the repository
root (gitignored), from `$FW_ENDPOINT` and `$FW_TOKEN`, or from `--endpoint` and
`--api-key`; the last one you set wins.

Every command documents its own flags with `--help`. The full references, with
everything above and more, live in [CONTRIBUTING.md](CONTRIBUTING.md),
[bots/README.md](bots/README.md), and [llm-bench/README.md](llm-bench/README.md).

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) explains how to write and submit a bot in six
  steps, and how to change the shared library or propose a new benchmark harness.
- [bots/README.md](bots/README.md) has the standings and explains how to play any
  shipped bot.
- [experiments/README.md](experiments/README.md) covers the research area behind the
  bots: training, sweeps, and what has already been tried.
- [llm-bench/README.md](llm-bench/README.md) covers the model benchmark: the harnesses,
  the standings, and how to read the table.
- [example.ipynb](src/pokelike/interfaces/python/example.ipynb) drives the game from a
  notebook, cell by cell.
- [bots/llm-example2/](bots/llm-example2/) shows how a bot works and everything you are
  allowed to change: the prompt, what the model sees, its memory, and its tools. Every
  setting is turned on, and each one has a line explaining what it does. It also
  includes [step.ipynb](bots/llm-example2/step.ipynb), which walks through one decision
  at a time: the state goes to the bot, you see what was sent to the model and what came
  back, and nothing moves until you run the next cell.

## Getting help

Open an issue on the [tracker](https://github.com/pierpierpy/pokelike.xyz.bot/issues).
A bug report about the shared code is the most useful thing you can send. Include a seed
and a step if you have one: running `uv run pokelike bot run --bot random --runs 1 -d`
prints every decision along with the screen it was made on.

## Maintainers & contributing

Maintained by [@pierpierpy](https://github.com/pierpierpy). The bot competition is open
to anyone: fork the repo, add a folder under `bots/`, and open a pull request. A
submission needs no permission and touches only your own folder. The full guide, and
the rules for changing the shared library or the benchmark, are in
[CONTRIBUTING.md](CONTRIBUTING.md).

The game itself is somebody else's fan project. Once you have the local copy, this
project generates no further traffic to them beyond the one-time download.
</content>
