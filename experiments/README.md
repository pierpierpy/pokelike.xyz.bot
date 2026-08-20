# experiments

**Yours is not tracked. Ours are, to be read.**

Anything you create under `experiments/` is gitignored, so what you try stays on
your machine and a pull request that adds a bot cannot drag six training runs
along with it. The folders below are ours and are checked in on purpose: they are
worked examples, and the point of them is that you can read what was actually
done rather than a description of it.

```
experiments/          research                 bots/          what it produced
├── env/       the problem, shared by all
├── example/   the smallest complete one                      start here
├── dyna-q/    tabular RL. It lost             dyna-q/        kept because it lost
├── sarsa/     linear FA. The one that worked  sarsa-v1/ -v2/ 81 and 100 features
├── llm/       comparing prompts               llm-*/         one harness, six bots
└── <yours>/   ignored by default, and yours   <yours>/
```

**An experiment is named after the bot it produces**, so you never have to work
out which folder trained what. `dyna-q/` trains `bots/dyna-q/`, `sarsa/` trains
both `sarsa-v*`, `llm/` compares the `llm-*` bots.

Hyphens are fine in a folder name even though they are not valid in an
identifier: `-m` takes a string and resolves it through the path finder, so
`python -m experiments.dyna-q.train` runs and the relative imports inside it
work. What you cannot write is `import experiments.dyna-q` in source.

Every one of them has the same shape, so moving between them costs nothing:

```
<experiment>/
├── README.md    what it asks, and what happened
├── agent.py     the thing being learned, if anything is
├── train.py     the loop
├── output/      weights and histories        (ignored)
└── logs/        what each run printed        (ignored)
```

Copy the one closest to your idea into `experiments/mine/` and work there.

**Contents**
- [What you have to show, and what you do not](#what-you-have-to-show-and-what-you-do-not)
- [What the area is for](#what-the-area-is-for)

- [`env/`](#env--the-game-as-an-rl-problem)
- [`example/`](#example--the-shape-with-nothing-clever-in-it)
- [Findings](#findings)
- [Measuring anything](#measuring-anything)

---

## What you have to show, and what you do not

Submitting a bot **does** reveal the bot: an entry archives the file that ran and
hashes it, and that is the only reason the number beside it means anything. A
leaderboard where the code is hidden is a list of claims.

Submitting does **not** reveal how you got there. The sweeps, the rewards you
tried, the prompts you threw away, the twenty runs that went nowhere, and that is
research, it lives here, and it stays yours.

You have to show what your bot does. Not how you arrived at it.

---

## What the area is for

A bot is one method: given the state, say which move to take. Everything that
goes into *deciding what that method should do* belongs here, so training a policy,
comparing prompts, sweeping hyperparameters, measuring whether an idea helps.

Nothing in `src/pokelike/` imports anything from here, and that is a rule rather
than an accident. The package is the environment; this is the research on top of
it. A submitted bot has to stand on its own, so if yours carries trained weights
the state encoding is frozen **inside the bot file** rather than imported from
here, because otherwise improving your training code would silently change what your
own past results meant. See [GUIDE.md](../GUIDE.md).

## `env/`, the game as an RL problem

The part every experiment shares, whatever it is doing.

| file | what it holds |
|---|---|
| `environment.py` | `TrainingEnv`: reset and step in RL terms |
| `rewards.py` | five reward functions, selectable by name |
| `encoding.py` | observation to a discrete state key, for tabular methods |
| `logs.py` | `tee()`: a run writes its own log into `<experiment>/logs/` |

**An MDP**, a Markov Decision Process, is the standard way of stating a problem
so Reinforcement Learning applies to it: states, the actions available in each,
and a reward. That is all `env/` is.

**Reward matters more than the algorithm here**, which is why it is a registry
rather than one function:

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

Careful with `game`. The engine's score formula was written for the Battle Tower
and two of its six terms never fire in Story mode, leaving `5·KO − 10·faints`,
a number that rewards fighting rather than getting further. It is why a run with
three badges can score −5.

## `example/`, the shape with nothing clever in it

```bash
uv run python -m experiments.example.train --episodes 20
```

It learns one number per node kind: how much that kind of node seems to be
worth. No state at all, so it will not beat much. It is here for the loop (play, score, update, save) which is what every experiment in this project has
been, with something better in the middle.

---

## Findings

Each folder's README has the detail. The results that shape how things are done
here. The numbers below are what a run measured at the time, kept as evidence;
for where anything currently stands, read the generated standings in
[bots/README.md](../bots/README.md) rather than this list.

**A tabular state key cannot see what decides this game.** `dyna-q` scored 0.62
badges on the benchmark against random's 0.56. On the starter screen its
learned values are 6.3 / 6.2 / 6.3 across three starters its six-number
encoding cannot tell apart: the information never reaches the table, so more
episodes do not change it.

**The representation is what beats random, not the algorithm.** `sarsa-v1` and
`sarsa-v2` scored 1.30 and 1.36 with the same algorithm family, reward and
budget as `dyna-q`. The difference between them and it is the feature vector.

**Feature-set differences sit below the noise floor.** Five variants, 23 to 100
features, all beat random (t between 2.4 and 4.3 paired) and none measurably
beats another (|t| below 1.7). The 0.06 badges between `sarsa-v1` and
`sarsa-v2` is smaller than the spread of the benchmark itself.

**Seed sets picked during development rank models wrongly.** One set of weights
scores 1.60 on the 25 seeds it was selected on and 1.10 on the official 50.
This is why there is exactly one measurement (below).

**A result you cannot replay is not a measurement.** An option's label carried a
pictograph the game substitutes when a sprite is missing from `site/`, and the
linear feature sets parse labels, so whether a 404 had come back decided a
feature vector, an argmax, and from there the whole run. Five of one entry's fifty
rows stopped reproducing, one of them by five badges. Before believing any number,
run the benchmark twice and check it agrees with itself; if the two disagree the
environment is the problem, not the policy.

**Fifty seeds cannot resolve what these experiments keep producing.** Badges vary
run to run with a standard deviation near 0.7, so fifty runs carry a standard
error near 0.1 and two bots need roughly 0.3 badges between them to be told apart.
Most differences measured here are smaller than that. Four hundred seeds costs
about ten minutes and resolves ~0.1, which is the difference between ranking
policies and ranking luck. Use the official 50 for submission and a wider block
for deciding what actually helped.

**Training runs being compared must share `--alpha-norm`.** The default step
normalisation divides by the number of active features, which is a property of
the feature set: without a shared constant, two variants differ in feature set
*and* effective learning rate, and the comparison answers neither. Left to the
default, small sets diverge, with weights of 10⁹ and beyond.

## Measuring anything

One way, the official benchmark, straight from where the bot lives:

```bash
uv run pokelike bench --bot experiments/mine --dry-run
```

The 50 fixed seeds everyone is scored on; measured by path it records nothing.
Compare the number with `uv run pokelike leaderboard`.

There is deliberately no second protocol. Runs vary enormously by luck, so any
seed set picked during development mostly measures who drew the nicer maps,
the section above has the demonstration: 1.60 on 25 development seeds, 1.10 on
the official 50, same weights. When your bot earns its place, bring it into
`bots/` the standard way and bench it there, under its own name.
