# AGENTS.md, experiments/

Details for the research area. The tour is [README.md](README.md); the cross-cutting
internals are in the root [AGENTS.md](../AGENTS.md).

- [What is tracked, and what is not](#what-is-tracked-and-what-is-not)
- [The shape of an experiment](#the-shape-of-an-experiment)
- [`env/`: the game as an MDP](#env-the-game-as-an-mdp)
- [Naming](#naming)
- [Measuring a candidate](#measuring-a-candidate)
- [Findings kept as evidence](#findings-kept-as-evidence)

---

## What is tracked, and what is not

`experiments/` is a scratch area. **Yours is not tracked; ours are, to be read.**
Everything under it is gitignored except the shared `env/`, `__init__.py`, and our own
worked examples (`example/`, `dyna-q/`, `sarsa/`, `llm/`, `drrn/`). Whatever you try
stays on your machine, and a pull request that adds a bot cannot drag a training run
along with it.

And regardless of any of that, a run's **output never commits**: three rules below the
opt-in block in `.gitignore` catch `experiments/*/output/`, `experiments/*/logs/`, and
`experiments/*/artifacts/` for every experiment, including whitelisted ones. `artifacts/`
is there because an experiment's `bot.py` is a *candidate*: its weights are training
output, and they only become something to commit when the bot earns a folder under
`bots/` and is measured there.

To publish your own, add one negation next to the others in `.gitignore`:

```
experiments/*
!experiments/env/
...
!experiments/mine/          # <- yours
```

Then `git add experiments/mine` picks up the **code and its README** and nothing else.
Check before committing, not after:

```bash
git status --short experiments/mine
git check-ignore -v experiments/mine/output/whatever.json   # should print the rule that caught it
```

**Nothing in `src/pokelike/` imports from here**, and that is a rule, not an accident.
The package is the environment; this is the research on top of it, and the package
cannot depend on files that are not in a clone.

## The shape of an experiment

Every one has the same shape, so moving between them costs nothing:

```
<experiment>/
├── README.md    what it asks, and what happened
├── agent.py     the thing being learned, if anything is
├── train.py     the loop
├── output/      weights and histories        (ignored)
└── logs/        what each run printed         (ignored)
```

Keep it that way when adding one. Copy the closest example into `experiments/mine/` and
work there.

## `env/`: the game as an MDP

The part every experiment shares, whatever it is doing. An MDP, a Markov Decision
Process, is the standard way of stating a problem so Reinforcement Learning applies:
states, the actions available in each, and a reward. That is all `env/` is.

| file | what it holds |
|---|---|
| `environment.py` | `TrainingEnv`: reset and step in RL terms |
| `rewards.py` | five reward functions, selectable by name |
| `encoding.py` | observation → a discrete state key, for tabular methods |
| `logs.py` | `tee()`: a run writes its own log into `<experiment>/logs/` |

**Reward matters more than the algorithm here**, which is why it is a registry:

```bash
uv run python -m experiments.example.train --reward badges
```

| reward | signal |
|---|---|
| `game` | the engine's own score |
| `badges` | the game's progress counter, and what the leaderboard ranks by |
| `progress` | badges, plus credit for getting deeper into a map |
| `survival` | staying alive; dense, and easy to learn the wrong lesson from |
| `composite` | a weighted mix |

Careful with `game`. The engine's score formula was written for the Battle Tower and
two of its six terms never fire in Story mode, leaving `5·KO − 10·faints`, a number
that rewards fighting rather than getting further, which is how a run with three badges
can score −5. See [AGENTS.md](../AGENTS.md#scoring) before designing any objective on
top of it.

## Naming

**An experiment is named after the bot it produces**, so you never have to work out
which folder trained what: `dyna-q/` → `bots/dyna-q/`, `sarsa/` → both `sarsa-v*`,
`llm/` → the `llm-*` bots.

Hyphens are fine in a folder name even though they are not valid in an identifier: `-m`
takes a string and resolves it through the path finder, so
`python -m experiments.dyna-q.train` runs and the relative imports inside it work. What
you cannot write is `import experiments.dyna-q` in source, and nothing needs to.

The one thing **not** renamed with a folder is `trainer:` inside an already recorded
`artifacts/config.json`: it names the script that produced those weights. Rewriting a
record to match a later rename is exactly what the fingerprint exists to prevent, and it
would mark rows stale for a cosmetic edit.

## Measuring a candidate

One way, the official benchmark, straight from where the bot lives:

```bash
uv run pokelike bot bench --bot experiments/mine --dry-run
```

The 50 fixed seeds everyone is scored on; measured by path it records nothing. Compare
the number with `uv run pokelike bot board`.

**There is deliberately no second protocol**, and no per-experiment evaluation script
with its own seed set. Runs vary enormously by luck, so any seed set picked during
development mostly measures who drew the nicer maps: the same weights score 1.60 on 25
development seeds and 1.10 on the official 50. Use the official 50 for submission and a
wider block (see below) for deciding what actually helped. When a candidate earns its
place, bring it into `bots/` the standard way and bench it there under its own name.

## Findings kept as evidence

Each folder's README has the detail; these are the results that shape how things are
done here. The numbers are what a run measured at the time, for where anything
currently stands, read the generated standings in [bots/README.md](../bots/README.md).

- **A tabular state key cannot see what decides this game.** `dyna-q` scored 0.62 badges
  against random's 0.56. On the starter screen its learned values are 6.3 / 6.2 / 6.3
  across three starters its six-number encoding cannot tell apart, so more episodes do
  not change it.
- **The representation is what beats random, not the algorithm.** `sarsa-v1` and
  `sarsa-v2` scored 1.30 and 1.36 with the same algorithm family, reward and budget as
  `dyna-q`. The difference is the feature vector.
- **Feature-set differences sit below the noise floor.** Five variants, 23 to 100
  features, all beat random (t between 2.4 and 4.3 paired) and none measurably beats
  another (|t| below 1.7).
- **Seed sets picked during development rank models wrongly.** 1.60 on the 25 seeds it
  was selected on, 1.10 on the official 50, same weights. This is why there is one
  measurement protocol.
- **A result you cannot replay is not a measurement.** A pictograph the game substitutes
  for a missing sprite got into an option's label, the linear features parse labels, and
  whether a 404 had come back decided a feature vector and from there the whole run.
  Five of one entry's fifty rows stopped reproducing. Run the benchmark twice and check
  it agrees with itself. See [AGENTS.md](../AGENTS.md#real-pitfalls).
- **Fifty seeds cannot resolve what these experiments keep producing.** Badges vary with
  a standard deviation near 0.7, so fifty runs carry a standard error near 0.1 and two
  bots need roughly 0.3 badges between them to be told apart. Four hundred seeds costs
  about ten minutes and resolves ~0.1.
- **Training runs being compared must share `--alpha-norm`.** The default step
  normalisation divides by the number of active features, a property of the feature set,
  so without a shared constant two variants differ in feature set *and* effective
  learning rate and the comparison answers neither. Left to the default, small sets
  diverge, with weights of 10⁹ and beyond.
