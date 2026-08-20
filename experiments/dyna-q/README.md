# Dyna-Q

**Contents**
- [The algorithm](#the-algorithm)
- [Why this algorithm first](#why-this-algorithm-first)
- [Two departures from the book](#two-departures-from-the-book)

- [Running it](#running-it)
- [Where to look when tuning](#where-to-look-when-tuning)

- [Results so far](#results-so-far)
- [Then it was given more, and it got worse](#then-it-was-given-more-and-it-got-worse)

---

Sutton & Barto, 2nd edition, **Chapter 8** "Planning and Learning with Tabular
Methods", **section 8.2** "Dyna: Integrated Planning, Acting, and Learning".

## The algorithm

Straight from the boxed pseudocode in section 8.2:

```
Initialise Q(s,a) and Model(s,a) for all s, a

Loop forever:
  (a) S  <- current (nonterminal) state
  (b) A  <- eps-greedy(S, Q)
  (c) Take action A; observe R, S'
  (d) Q(S,A) <- Q(S,A) + alpha [R + gamma max_a Q(S',a) - Q(S,A)]
  (e) Model(S,A) <- R, S'
  (f) Loop n times:
        S      <- random previously observed state
        A      <- random action previously taken in S
        R, S'  <- Model(S,A)
        Q(S,A) <- Q(S,A) + alpha [R + gamma max_a Q(S',a) - Q(S,A)]
```

Steps (a) to (d) are plain **Q-learning** (section 6.5). Everything Dyna adds is
(e) and (f): a learned model of the environment, and `n` extra updates per real
step drawn from remembered experience.

In `agent.py` those map to `observe()` for (d) and (e), and `plan()` for (f).

## Why this algorithm first

Because the environment is slow. A real step drives a browser and costs about a
quarter of a second; a planning update is a dict lookup and a bit of arithmetic.
Dyna exists precisely for that trade-off, and this problem happens to fit the
motivation almost too well.

Measured on a 20-episode run: **380 real steps produced 7749 Q updates**. Same
wall clock, twenty times the learning.

## Two departures from the book

**1. The action set changes with the state.** In the maze of section 8.2 every
state offers the same four moves, so `max_a Q(S',a)` ranges over a fixed set.
Here a turn offers 2 to 7 options and they differ every time, so the model
stores which actions were legal in `S'` and the max is taken over those.
Maximising over unavailable actions would leak value from moves that cannot be
played.

**2. The model is deterministic, the game is not.** The book's Dyna-Q assumes a
deterministic environment and keeps one `(R, S')` per pair. Battles roll damage,
so the same `(S, A)` can lead elsewhere. We keep the book's assumption
deliberately: it is the simplest thing that works, and the compressed state hides
much of the variation. It is also the first thing to revisit if learning
plateaus, either stochastic Dyna-Q with outcome counts, or **Dyna-Q+**
(section 8.3).

## Running it

```bash
# train (about 15 minutes for 50 episodes)
uv run python -m experiments.dyna-q.train --episodes 50

# how good is it? the official benchmark, straight from this folder
uv run pokelike bench --bot bots/dyna-q --dry-run
```

| flag | meaning | default |
|---|---|---|
| `--episodes` | how many runs to learn from | 200 |
| `--planning-steps` | the `n` of the algorithm box | 20 |
| `--alpha` | step size | 0.1 |
| `--gamma` | discount | 0.95 |
| `--epsilon` | initial exploration, annealed to 0.02 | 0.3 |
| `--optimistic` | initial Q; > 0 encourages early exploration | 0.0 |
| `--fixed-seed` | replay the same run every episode | off |
| `--seed0` | seed of the first episode | 1 |

`--fixed-seed` is the sanity check worth running first: on a single repeated run
the agent should get visibly better within a few dozen episodes. If it does not,
the bug is in the encoding or the reward, not in the hyperparameters.

## Where to look when tuning

**`--planning-steps` is the cheap knob.** It costs no browser time. Raising it
to 50 is nearly free in wall clock. Diminishing returns come from the model
being wrong (see departure 2), not from cost.

**The encoding matters more than the hyperparameters.** `env/encoding.py`
decides what the agent can even distinguish. If two situations that need
different moves collapse into the same key, no amount of `alpha` will save it.

**`gamma` at 0.95 over 15-to-35-step episodes** means the +500 for finishing is
discounted to roughly 500 × 0.95³⁰ ≈ 107 at the start of a run. Since almost no
early run finishes, that term does very little in practice; the learning signal
that actually drives things is +50 per map cleared.

## Results so far

Trained on 90 episodes (n=30 planning steps, 22 minutes, 569 states discovered,
46159 Q updates), then benchmarked on the 50 standard seeds against the random
baseline. Both played **the same seeds**, so this is a paired comparison.

```
                score~  stdev   worst   best   steps~  faints~
dyna-q v1          4.9   26.8     -70     85     29.7      3.0
random            -3.5   20.9     -55     65     17.1      4.1

paired difference: +8.4 per seed, t = 1.70
wins 24, draws 6, losses 20
```

**Read this honestly.** t = 1.70 is not significant: with 50 seeds and this much
variance, +8.4 points could be luck. Winning 24 of 50 is barely a coin flip.

But two numbers are not ambiguous at all. The agent **survives 74% longer**
(29.7 steps against 17.1) and **loses a quarter fewer Pokemon** (3.0 faints
against 4.1). It clearly learned the part of the reward it was hit with most
often: -10 every time something faints.

What it did **not** learn is to make progress. `maps cleared` is 0 for both, and
that is where the +50s live. So the policy is currently a good survivor and a bad
climber, which makes sense: staying alive is rewarded locally and constantly,
while clearing a map is a long chain of decisions ending in a single payout that
90 episodes almost never reached.

That is the thing to attack next, and it points at the algorithm rather than the
hyperparameters: sparse delayed reward is what n-step methods (Chapter 7) and
prioritised sweeping (8.4) are for.

## Then it was given more, and it got worse

That last paragraph turned out to be wrong, and the record is left standing
rather than edited into something that looks smarter.

Version 2 of the encoding fixed the fragmentation described above (563 states
holding 686 pairs became 397 holding 940) and it trained for 400 episodes with
50 planning steps, 465k updates. Evaluated greedily on 20 held-out seeds against
random on the same seeds:

```
               mean score   wins
dyna-q v2            -3.8    6/20   (2 draws, 12 losses)
random                7.0
```

It **lost**. More episodes, a better-conditioned table, and it went backwards.

The detailed log had already said why, before either evaluation:

```
    1 | starter-screen
      | [0] Bulbasaur Lv5  [1] Charmander Lv5  [2] Squirtle Lv5
      |    Q: slot0=6.3, slot1=6.2, slot2=6.3
```

Three values within a rounding error, because the encoding shows the agent three
indistinguishable slots where a player sees a Grass starter, a Fire one and a
Water one with different stats. **No number of episodes fixes that: the
information never reaches the table.**

So the diagnosis in the previous section, attack the algorithm, was the wrong
call. The limit was the representation. [`sarsa/`](../sarsa/) is
that hypothesis tested: same reward, same environment, same held-out protocol,
81 linear features instead of a table (100 since). It won 15 of 25 with no
losses, and the trained rows it produced are near the top of the standings.

The tabular version is kept because a Q-table is the clearest thing to read when
you want to know what an agent believes, and because a negative result you can
reproduce is worth more than one you quietly delete.
