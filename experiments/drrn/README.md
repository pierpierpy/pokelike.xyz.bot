# A network where SARSA has a dot product

    q̂(s, a) = MLP(x(s, a))          against        q̂(s, a) = wᵀ x(s, a)

The intent is one variable: the shape of q̂. This experiment uses the same 100
features, the same reward, and the same benchmark as the linear SARSA bot.

Reaching that intent takes a second arm. Comparing an offline-fitted network
against `sarsa-v2` moves three things at once: the model, the algorithm
(on-policy SARSA(λ) online, against fitted Q iteration offline), and the data
(self-played, against mostly random). Measured, the algorithm and the data cost
−0.56 badges between them, which is larger than anything the model was expected
to buy. So q̂ = wᵀx is fitted by the *same* pipeline on the *same* shards, and it
is that pair which isolates capacity, not the comparison with the standings.

Contents
- [What it asks](#what-it-asks)
- [Why a network, given the linear model plateaued](#why-a-network-given-the-linear-model-plateaued)
- [Why the data comes first](#why-the-data-comes-first)
- [Running it](#running-it)
- [Layout](#layout)
- [What would refute it](#what-would-refute-it)
- [What happened](#what-happened)

---

## What it asks

Three things have been tried on the linear model and none of them moved the
benchmark:

| | badges |
|---|--:|
| more episodes, 300 → 1200 | +0.02 |
| dropping the features that cannot decide | −0.02 |
| more features, 81 → 100 | +0.06 |

The standard error of the mean over 50 seeds is about 0.1 badges, so all three
are noise. The budget is not the limit and the choice of features is not the
limit. What is left is what the model can express given them.

## Why a network, given the linear model plateaued

Read the weights the linear model learns and the largest by far, namely `team_size`,
`bias`, `map_index` and `badges`, are all state-only. They read the same for
every action available in a state, so they shift each option by the same amount
and cancel in the argmax: they cannot change a single decision. Measured on a
real state, 8 of the 17 active features are in that position and they carry 475
of the 552 total weight.

The obvious conclusion, that they are dead weight, is wrong: dropping them
scores 1.36 against 1.38, which is the same. These features are not useless,
but they are also not policy-relevant on their own. They are a term that only
means anything crossed with the action, since how much a trainer node is worth
depends on how small the team is.

A linear model can only carry such a cross if a person writes the product down,
and three are written down today (`node:trainer*small_team` and two others; one
of them is among the few large weights that *can* decide). A hidden layer builds
those products out of the same inputs without anyone choosing which.

That is the hypothesis in one line: the features are fine and the model cannot
combine them.

## Why the data comes first

Collecting and fitting are bound by different things. Playing is bound by the
browser (one per process, about a quarter of a second a decision) while fitting
a small network to a fixed array is bound by arithmetic and wants everything in
memory at once. Because the work is split, one machine collects with every core
it can keep busy and then fits as often as it likes.

Measured, on 22 cores: 8 collectors is the knee. Twelve buys 7% over eight
(1.26 against 1.18 episodes a second), because once the virtual clock removed the
waiting the work is CPU-bound and the cores are full. 4000 episodes took 55
minutes and produced 107k transitions.

So: collect once in parallel, then fit offline as many times as you like. Thirty
rounds of fitted Q iteration over the whole dataset take 1.6 minutes, about
fifteen episodes of play, against the hour the dataset cost. That ratio is the
whole reason for the split: the variants are nearly free; the data is not.

Fitted Q iteration (Ernst, Geurts & Wehenkel, JMLR 2005) treats improvement as a
sequence of ordinary regressions: round *k* builds `y = r + γ·max_a' Q_{k-1}(x')`
for every transition and fits `Q_k` to it. This is why collection records the
features of every action available at the next decision point, not just the
one that was taken. The max needs them, and a dataset without them can only
evaluate the policy that produced it.

The behaviour policy is deliberately mixed, half guided and half random. Data
drawn only from a good policy contains no examples of where the bad options
lead, which is precisely what a max over actions has to know.

Between rounds the network can be periodically re-initialised while the data is
kept, on the argument that reusing one dataset overfits a network to whatever it
saw first, the primacy bias (Nikishin et al., arXiv:2205.07802).

That argument does not survive contact with this loop, and the reason is worth
writing down. The improvement is *not* carried by the targets, because the
targets are rebuilt from the current network at the top of every round: a reset
the model cannot re-fit immediately is thrown away, not banked. Measured on the
linear arm, where six epochs cannot re-fit what was discarded, the loss spikes
from 625 to 2838, mean q collapses from 48.6 to 8.5, and round 29 finishes
*below* round 9. The next round's targets are then built from the damaged net, so
the loss compounds. The 64·64 net absorbs it, loss 353 to 488 with mean q barely
dipping, which is why it went unnoticed. Use `--reset-every 0` for anything
whose capacity is small enough to notice.

## Running it

Numpy is not a project dependency, because a bot has to load in any checkout, so it
comes in for the command and leaves again:

```bash
# 1. collect, in parallel, once. 55 minutes on 22 cores
uv run --with numpy python -m experiments.drrn.collect \
    --episodes 4000 --workers 8 --tag mixed \
    --weights bots/sarsa-v2/artifacts/weights.json

# 2. fit, offline, as often as you like. Under 2 minutes a round-trip
uv run --with numpy python -m experiments.drrn.train --data mixed --iters 30
uv run --with numpy python -m experiments.drrn.train --data mixed --iters 30 \
    --hidden '' --reset-every 0 --out linear.json      # the control arm

# 3. measure, the one way there is
cp experiments/drrn/output/models/drrn.json experiments/drrn/artifacts/weights.json
uv run pokelike bot bench --bot experiments/drrn
```

Every command is run from the repository root, including the `cp`, because the
`-m` flag needs it, so the paths are written out in full rather than relative to
this folder. Running `bot bench` needs no `--dry-run` here, since a bot measured
by path records nothing either way.

| flag | meaning | default |
|---|---|---|
| `--workers` | parallel collectors, one browser each. 8 saturates 22 cores | 1 |
| `--random-share` | share of episodes played at random | 0.5 |
| `--epsilon` | exploration on the guided episodes | 0.25 |
| `--iters` | fitted Q rounds | 30 |
| `--hidden` | layer sizes; `''` or `linear` fits wᵀx, the control arm | `64,64` |
| `--reset-every` | re-initialise the network every N rounds; 0 disables | 10 |
| `--epochs` | passes over the data per round | 6 |

The trained net exports as JSON and the bot does the forward pass in plain
Python, so nothing a submission plays needs numpy installed. Two tests hold that
together, because either drift would be silent: one checks the two
implementations of the arithmetic against each other; the other checks that the
features frozen inside `bot.py` compute the same vectors as the ones `collect.py`
and `train.py` import. Both sides keep 100 features and nothing raises, so a
drift there would fit one feature map and benchmark another.

## Layout

```
drrn/
├── agent.py     the network: forward, backprop, Adam, reset, export
├── collect.py   play episodes, write transitions, fan out over processes
├── train.py     fitted Q iteration over a collected dataset
├── measure.py   the official 50, with the per-seed rows kept for a paired test
├── bot.py       the player: frozen features, pure-Python forward pass
├── artifacts/   the weights the bot reads
├── output/      data shards, models, histories   (gitignored)
└── logs/        what each run printed            (gitignored)
```

The `measure.py` script imports `STANDARD_SEEDS` and `run_benchmark`, so it is the
official benchmark to the letter and chooses no seed of its own. What it adds is
that the fifty per-seed rows survive, which is what makes a comparison paired:
two means over 50 seeds cannot resolve less than about 0.39 badges; the same
runs compared seed by seed resolve about 0.25.

## What would refute it

A benchmark number at or below 1.36 would say the features are the ceiling, and
that capacity on top of them buys nothing, which would make the next thing
worth trying a change to what the agent can see, not to how it combines what it
already sees.

It is worth being clear in advance: 1.38 would not be a win either. Two bots need
roughly 0.3 badges between them to be distinguishable over 50 seeds.

## What happened

The paragraph above is left exactly as it was written before the run, because the
run fired it and the inference it licenses is wrong.

This run played 4000 episodes, produced 107,355 transitions, and took 55
minutes. Every arm was measured once on the official 50 seeds, paired against
`sarsa-v2`'s recorded per-seed rows:

| arm | badges~ | steps~ | vs `sarsa-v2`, paired |
|---|--:|--:|---|
| `64,64`, `--reset-every 10`, the pre-registered one | 1.18 | 118.7 | −0.18, t = −1.70 |
| `64,64`, `--reset-every 0` | 1.16 | 171.5 | −0.20, t = −1.75 |
| **`wᵀx`, same pipeline, the control** | **0.80** | 21.5 | −0.56, t = −5.62, 0W-28D-22L |
| `sarsa-v2`, for reference | 1.36 | 19.0 | n/a |

Read against the standings alone, 1.18 says *the features are the ceiling*. The
control says that is backwards:

- Going offline costs 0.56 badges. The control is the same functional form as
  `sarsa-v2` over the same features, and it loses 22 of 50 seeds while winning
  none. Fitted Q iteration on a dataset that is 62.5% random actions is much worse
  than online SARSA(λ) for an identical model.
- Capacity is worth +0.36 badges, t = 3.67, 15W-34D-1L, with data, targets,
  rounds, γ and epochs all held fixed. The hidden layer recovers most of what the
  pipeline gave away. It does not fail to help.
- The reset is worth nothing to the network, +0.02, t = 0.24, and considerable
  damage to the control, as above.

And the network is not usable, for a reason unrelated to any of that. Look at
`steps~`: 20 of its 50 runs never reach game over. They end at the 400-step cap,
on `item-screen` and `item-equip-modal`, ping-ponging:

```
step 396  item-equip-modal  ['EQUIP:Wartortle Lv17','KEEP IN BAG','CANCEL']  -> CANCEL
step 397  item-screen       ['Choice Scarf','Lagging Tail','Metronome']      -> Metronome
step 398  item-equip-modal  ['EQUIP:Wartortle Lv17','KEEP IN BAG','CANCEL']  -> CANCEL
step 399  item-screen       ['Choice Scarf','Lagging Tail','Metronome']      -> Metronome
```

That run alone logs 191 CANCELs. The control never does it; `sarsa-v2` never does it.

The values are not the culprit, which is the instructive part of this failure. Mean q̂ is 1.3-1.5×
the dataset's own discounted return-to-go, which is what a greedy estimate over a
mostly-random behaviour policy *should* look like, and the ceiling (230) sits below
the data's 99th percentile (322). Nothing diverged. The error is total but local,
on one action the data does not constrain:

- A cycle pays 0 for ever, so its true value is 0. Thirty rounds of fitted Q
  iteration propagate consequences thirty steps, and γ³⁰ = 0.55: a trap that only
  bites after hundreds of steps is invisible at that depth.
- Cancelling looks free for one step and lands on a screen whose max is high.
- The behaviour data contains 2-3 step cycles and never long ones, because random
  play escapes the modal with probability 2/3 per visit.
- And the reward has no cost of time: the `progress` reward pays nothing for a
  wasted turn, so looping is not merely tolerable; it is free.

The cheapest next test needs no new data: run more rounds and watch whether the
cycle's value collapses once the propagation is deep enough to reach it. After
that, try a small per-step penalty, but that changes the reward, so `sarsa-v2`
would have to be retrained on it before the comparison meant anything again.
