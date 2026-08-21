# experiments

**Yours is not tracked. Ours are, to be read.**

Anything you create under `experiments/` is gitignored, so what you try stays on your
machine and a pull request that adds a bot cannot drag six training runs along with it.
The folders below are ours and are checked in on purpose: worked examples you can read,
rather than a description of them.

```
experiments/          research                 bots/          what it produced
├── env/       the problem, shared by all
├── example/   the smallest complete one                      start here
├── dyna-q/    tabular RL. It lost             dyna-q/        kept because it lost
├── sarsa/     linear FA. The one that worked  sarsa-v1/ -v2/ 81 and 100 features
├── llm/       comparing prompts               llm-*/         one harness, six bots
└── <yours>/   ignored by default, and yours   <yours>/
```

An experiment is named after the bot it produces, and every one has the same shape
(`README.md`, `agent.py`, `train.py`, `output/`, `logs/`). Copy the one closest to your
idea and work there:

```bash
cp -r experiments/example experiments/mine
uv run python -m experiments.example.train --episodes 20   # the shape of one
uv run python -m experiments.sarsa.train --episodes 300    # the real thing
```

**`env/`** is the part every experiment shares: the game stated as an RL problem, with a
registry of reward functions selectable by name (`--reward badges`). Reward matters more
than the algorithm here.

Measure a candidate right where it lives — the official 50 seeds, recorded nowhere:

```bash
uv run pokelike bot bench --bot experiments/mine --dry-run
```

When it earns its place, bring it into `bots/` the standard way and bench it there.

The reward registry, the naming rules, how to publish your own experiment, and the
findings that shaped how things are done here are in [AGENTS.md](AGENTS.md). Writing and
submitting a bot is [CONTRIBUTING.md](../CONTRIBUTING.md).

---

**What you have to show, and what you do not.** Submitting a bot reveals the bot: an
entry archives the file that ran and hashes it, and that is the only reason the number
beside it means anything. It does **not** reveal how you got there — the sweeps, the
rewards you tried, the twenty runs that went nowhere. That is research, it lives here,
and it stays yours. You show what your bot does, not how you arrived at it.
