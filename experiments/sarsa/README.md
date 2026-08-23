# SARSA(λ) with linear function approximation

Sutton & Barto, 2nd edition, chapter 10, "On-policy Control with
Approximation," covers the semi-gradient control update. Section 12.7 covers
the SARSA(λ) form.

    q̂(s, a, w) = wᵀ x(s, a)

Contents
- [Why, after Dyna-Q](#why-after-dyna-q)
- [What changes](#what-changes)
- [No neural network, on purpose](#no-neural-network-on-purpose)

- [Results](#results)
- [Which features actually decide anything](#which-features-actually-decide-anything)
- [You can read what it learned](#you-can-read-what-it-learned)

- [Layout](#layout)
- [Running it](#running-it)
- [Where to look if it stalls](#where-to-look-if-it-stalls)

---

## Why, after Dyna-Q

Tabular Dyna-Q was given a fair run: 400 episodes, encoding v2, 50 planning
steps, 465k updates. It was evaluated greedily on 20 held-out seeds against
random on the same seeds:

```
               mean score   median   worst   best
dyna-q               -3.8      7.5     -75     40
random                7.0      7.5     -50     50

paired: dyna-q wins 6/20, draws 2, loses 12
```

It lost. And the detailed log said why long before the evaluation did:

```
    1 | starter-screen
      | [0] Bulbasaur Lv5  [1] Charmander Lv5  [2] Squirtle Lv5
      |    Q: slot0=6.3, slot1=6.2, slot2=6.3
```

The three values sit within a rounding error of each other, because the
encoding shows the agent three indistinguishable slots. A player sees a
Grass/Poison starter, a Fire one and a Water one, each with different stats.
No number of episodes fixes that: the information never reaches the table.

So the problem was the representation, not the algorithm: the agent could not
distinguish situations that needed different moves.

## What changes

The agent can see. Features carry what is on screen: a candidate's types,
whether they are new to the team, its bulk against the other two on offer, and
where a map node leads. The `features/groups.py` module parses the Pokemon
card text the tabular agent threw away.

The agent generalises. Weights are shared, so "catch something that adds a
type I lack" is learned once and applies everywhere, instead of being
relearned in each table cell. That matters here more than usual: every real
step costs half a second of browser, so the sample budget is a few thousand
transitions, not millions.

Credit reaches back. Badges arrive many decisions after the choices that
earned them. A one-step backup moves credit one step per visit; λ = 0.9
spreads it down the whole chain at once.

Actions stay distinct. The agent drives `Game` by action index rather than by
key, so the five EQUIP buttons are five actions with five feature vectors. The
tabular agent collapsed them into one `btn:equip` and could not choose *who*
to equip.

The agent decides the team order (feature set v2). Slot 0 leads the next
battle, and reordering costs no turn, so the reorder decision is modelled as an
extra state in the MDP with reward 0, not an extra action in the existing one. The state's
options are "leave it" plus "bring slot j to the front", scored by the same q̂
and the same weights, and SARSA(λ)'s traces carry the credit back through the
swap on their own. Reordering is available in about 61% of turns.

Every `order:` feature is a difference against the current leader, or an
interaction with the leave-it option, because one that read the same for every
option would cancel in the argmax and decide nothing.

The agent can read an item and a move. Feature set v2 also added the `item:`
and `tutor:` groups. Without them, item and tutor screens are invisible to the
vector: q-values come out identical across a Red Card, a Moon Stone and an
Assault Vest, and the agent chooses among them at random.

The `item:` group reads the two things the engine actually keeps structured:
the item id, and `TYPE_ITEM_MAP`, which turns eighteen near-identical "+40%
X-type damage" items into one question: does this boost a type I field. The
group deliberately encodes no magnitudes: those live inline in the battle code
keyed by id, so a table of them would have to be copied out of the bundle and
would keep reporting the old numbers after any upstream rebalance, silently.

The `tutor:` group compares the offer against what that Pokemon already uses.
The button text carries neither power nor type, but the engine builds it with
`getBestMove(..., moveTier + 1, ...)`, so asking the same question gives the
offer with both: Bulbasaur uses Magical Leaf at 40, and the tutor offers
Energy Ball at 90.

That makes 100 features, in index order: `context` 9, `node` 12, the three node
crosses 36, `lookahead` 4, `screen` 7, `mon` 7, `slot` 3, `button` 3, `item` 7,
`tutor` 5, `order` 7.

## No neural network, on purpose

The reason is a sample budget constraint. An episode is about 20 transitions, so
300 episodes is a few thousand transitions, and a DQN's usual budget is
10⁵-10⁶: on the order of an hour for the low end once collection runs in
parallel processes, and a long day for the high end. The binding constraint is
samples, not model capacity, and hand-built features plus a linear model is
what that budget buys.

If hand-built features turn out to be sufficient, that result is the evidence
that would justify learning a representation instead of writing one.

## Results

This run used 300 episodes with reward `progress`, took 98 minutes, and
produced 5988 updates. Evaluation then ran greedily on seeds 40000-40024,
which training never touched, against random on those same seeds:

```
            badges~  badges+   steps~  faints~   score~
sarsa          1.52        5     21.9      3.0     67.6
random         0.64        2     17.6      4.0      3.2

paired: sarsa wins 15, draws 10, loses 0 out of 25
mean difference: +0.88 badges per run       t = 4.18
```

There was not one loss in 25, and the draws are nearly all 0-0 on seeds where
both runs die early. This evaluation used the same environment, the same
reward, and the same held-out protocol on which tabular Dyna-Q went backwards
(−3.8 against random's 7.0). The change was the representation, and that was
the hypothesis.

The learning curve says the same thing about sample cost:

```
ep   0-24   0.84 badges     <- random gets 0.68
ep  25-49   1.20
ep  50-74   1.56            <- most of it, in fifty episodes
ep  75-99   1.20
ep 275-299  1.12
```

The numbers above show badges per episode, in blocks of 25, from
`output/runs/sarsa_v1_history.json`. The gain arrives in about 50 episodes,
roughly 1000 transitions, and then not only flattens but drifts back down as
epsilon anneals. Dyna-Q had 400 episodes and never left the floor.

The largest weights cannot change a single choice, but this is expected and not
a flaw. The features `team_size`, `bias`, `map_index` and `badges`, which carry the
heaviest weights, are all state-only: they shift every action in a state by
the same amount and cancel in the argmax. They stay in the feature set because
they carry the *level* of the return, which the bootstrapped target is built
out of; measured, cutting them does not help (the comparison below). These
features still contribute to learning even though they cannot decide.

## Layout

```
sarsa/
├── agent.py          the algorithm: q̂ = wᵀx, traces, the update
├── train.py          the one thing you run
├── features/         THE REPRESENTATION, the part worth arguing about
│   ├── groups.py       the 100 features, in named groups
│   └── variants.py     which groups a run carries, and what it is asking
├── logs/             what each run printed, written by the run (gitignored)
└── output/           weights and histories (gitignored)
```

The `features/` directory is its own package because the Dyna-Q experiment
showed that the feature vector matters more than the update rule. Keeping the
features separate makes it possible to switch a group off and leave everything
else meaning the same thing.

## Which features actually decide anything

Train a variant by naming its groups, then measure it like everything else,
against the official benchmark, from wherever the weights are:

```bash
uv run python -m experiments.sarsa.train --episodes 300 --groups node,mon,lookahead --out candidate.json
uv run pokelike bot bench --bot experiments/mine --dry-run
```

Every variant is a question with an answer you can be wrong about, written
down in `features/variants.py` before the run, so the result cannot be
reinterpreted after the fact.

One training run is about 100 minutes. At that cost a serial experiment tests
two ideas and stops, so running variants in parallel matters. Each variant runs
in its own process with its own browser.

The parallelism is deliberately between runs and never inside one. SARSA is
on-policy with eligibility traces: splitting episode collection across several
environments would draw updates from a behaviour distribution the traces do
not describe, which would make it a different algorithm despite the same code.
Whole independent runs sidestep that, and comparing variants is exactly the case
where that is all you need.

A variant that drops features and does not get worse is the interesting
result, not a disappointing one: it means those features were never doing the
work their weights suggested.

### What the variants measure, and what they cannot

Five feature sets were trained for 300 episodes each, all sharing
`--alpha-norm 9.0`, and measured paired against random on the same seeds:

```
variant           feats   badges~   vs random      t
full                100      1.60   14W-11D-0L   3.43
action-only          84      1.36   13W-10D-2L   2.42
minimal              23      1.24    13W-9D-3L   3.00
no-v2                81      1.20   14W-10D-1L   4.30
no-interactions      64      1.12   11W-13D-1L   3.12
random                       0.64
```

Every variant beats random. No variant beats another: paired between
themselves, every difference sits at |t| below 1.7, so the ranking down the
left column carries no information. Separating feature sets at this variance
needs on the order of a hundred runs per variant, or a measurement with less
variance in it than badges over a whole run.

Two rules follow, and both are load-bearing:

- Only the official benchmark ranks a model. The same `full` weights score
  1.60 on 25 seeds chosen during development and 1.10 on the official 50, a
  gap wider than any in the table.
- Runs being compared share `--alpha-norm`. The default step normalisation
  divides by the count of active features, which is a property of the feature
  set (9.0 per (s, a) for `full`, 1.2 for `minimal`): without a shared
  constant, two variants differ in feature set *and* effective learning rate,
  and the smaller sets diverge, with weights of 10⁹ and beyond.

## Running it

```bash
uv run python -m experiments.sarsa.train --episodes 300 --reward progress
uv run pokelike bot bench --bot experiments/mine --dry-run    # measure: official 50, records nothing
```

| flag | meaning | default |
|---|---|---|
| `--alpha` | step size, divided by the number of active features | 0.05 |
| `--gamma` | discount | 0.98 |
| `--lam` | trace decay λ | 0.9 |
| `--epsilon` | initial exploration, annealed to 0.02 | 0.3 |
| `--reward` | which reward (see `env/rewards.py`) | progress |
| `--out` | *train*: file to write in `output/models/` | `sarsa.json` |
| `--groups` | feature groups to keep, comma separated | all |
| `--alpha-norm` | shared step divisor, same value across runs you compare | per-feature |

The `--out` flag deliberately does not default to a name a submitted bot
reads. Both [`bots/sarsa-v1/`](../../bots/sarsa-v1/) and
[`bots/sarsa-v2/`](../../bots/sarsa-v2/) load `artifacts/weights.json` from
inside their own folder and nowhere else, so a training run cannot silently
replace a policy that is on the standings.

## Measuring a candidate

Write the bot inside your experiment folder and point the benchmark at it:

```bash
uv run pokelike bot bench --bot experiments/mine --dry-run
```

A bot measured by path is never recorded. The run prints its numbers on the
official 50 seeds and that is all. Compare them with `pokelike bot board`.
When it earns its place, bring it into `bots/` the standard way, with
`pokelike bot new` or by copying your `bot.py` and artifacts into a folder of its
own, and bench it there under its own name. A candidate is never measured under
another bot's name.

## You can read what it learned

This is the point of a linear model. Training prints the weights the model
leaned on hardest, and they are named:

```
what it leaned on:
  team_size                  -129.276
  bias                         93.125
  map_index                   -79.623
  ...
  node:trainer*small_team      29.392
  mon_new_type                 18.384
  mon_best_stats               17.706
```

Those are named weights you can argue with, unlike a value table of 400 opaque
cells. The first three depend on the state and not the action, so they add
the same number to every option and cancel in the argmax. See the weights
note under *Results* for why they stay anyway.

## Where to look if it stalls

Look at the features before the hyperparameters. If two situations that need
different moves produce the same vector, no step size will separate them. The
`feature_names()` function is the whole vocabulary the agent has.

α is normalised per active feature, so that adding features does not silently
multiply the effective learning rate. That mistake looks exactly like the
algorithm being unstable.

Linear approximation plus bootstrapping can diverge (chapter 11, the deadly
triad). SARSA is on-policy, which removes one leg of the triad, but if weights
start growing without bound the step size is the first suspect.
