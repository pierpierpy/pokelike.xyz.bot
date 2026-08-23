# experiments

Your own experiments are not tracked. The experiments checked in here are tracked, and
they are meant to be read as worked examples.

Anything you create under `experiments/` is gitignored, so what you try stays on your
machine and a pull request that adds a bot cannot drag six training runs along with it.
The folders below are checked in on purpose: they are the worked examples you can read
and copy, showing how each approach was trained and measured.

```
experiments/          research                 bots/          what it produced
├── env/       the problem, shared by all
├── example/   the smallest complete one                      start here
├── dyna-q/    tabular RL. It lost             dyna-q/        kept because it lost
├── sarsa/     linear FA. The one that worked  sarsa-v1/ -v2/ 81 and 100 features
├── llm/       comparing prompts               llm-*/         one harness, six bots
└── <yours>/   ignored by default, and yours   <yours>/
```

---

**Contents**

- [The layout](#the-layout)
- [`env/` and rewards](#env-and-rewards)
- [Measuring a candidate](#measuring-a-candidate)
- [What you show, and what you keep](#what-you-show-and-what-you-keep)

---

## The layout

An experiment is named after the bot it produces, and every one has the same shape
(`README.md`, `agent.py`, `train.py`, `output/`, `logs/`). Copy the one closest to your
idea and work there:

```bash
cp -r experiments/example experiments/mine
uv run python -m experiments.example.train --episodes 20   # the shape of one
uv run python -m experiments.sarsa.train --episodes 300    # the real thing
```

## `env/` and rewards

The `env/` folder is the part every experiment shares: it states the game as a
reinforcement-learning problem (observations, actions, transitions), with a registry
of reward functions selectable by name (`--reward badges`). The choice of reward
matters more than the choice of algorithm here, because the engine's own score formula
is a Battle Tower formula that barely moves in Story mode.

## Measuring a candidate

Measure a candidate right where it lives, using the official 50-seed benchmark that
all bots in the standings are scored on. The `--dry-run` flag plays all fifty seeds
but records nothing:

```bash
uv run pokelike bot bench --bot experiments/mine --dry-run
```

When a candidate earns its place, bring it into `bots/` the standard way and bench it
there. [CONTRIBUTING.md](../CONTRIBUTING.md) explains how to write and submit a bot.

## What you show, and what you keep

Submitting a bot reveals the bot: an entry archives the file that ran and hashes it,
and that hash (the fingerprint) is the only reason the number beside the entry means
anything. The submission does not reveal how you got there: the sweeps, the rewards you
tried, the twenty runs that went nowhere. That is research. It lives here, and it stays
yours. A submission shows what your bot does; the process that produced it stays private.
