# Dyna-Q

Contents
- [The algorithm](#the-algorithm)
- [Why this algorithm first](#why-this-algorithm-first)
- [Two departures from the book](#two-departures-from-the-book)

- [Running it](#running-it)
- [Where to look when tuning](#where-to-look-when-tuning)

- [Results so far](#results-so-far)
- [Then it was given more, and it got worse](#then-it-was-given-more-and-it-got-worse)

---

The algorithm below comes from Sutton & Barto, 2nd edition, Chapter 8 "Planning and Learning with Tabular Methods", section 8.2 "Dyna: Integrated Planning, Acting, and Learning".

## The algorithm

The pseudocode below comes straight from the boxed algorithm in section 8.2:

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

Steps (a) to (d) are plain Q-learning (section 6.5). Everything Dyna adds is in steps (e) and (f), which provide a learned model of the environment and `n` extra updates per real step drawn from remembered experience.

In `agent.py`, the steps map to `observe()` for (d) and (e), and to `plan()` for (f).

## Why this algorithm first

This algorithm comes first because the environment is slow. A real step drives a browser and costs about a quarter of a second, while a planning update is a dict lookup and a bit of arithmetic. Dyna exists precisely for that trade-off, and this problem happens to fit the motivation almost too well.

Measured on a 20-episode run, 380 real steps produced 7749 Q updates. The wall clock time was the same, but the amount of learning was twenty times greater.

## Two departures from the book

1. The action set changes with the state. In the maze of section 8.2 every state offers the same four moves, so `max_a Q(S',a)` ranges over a fixed set. Here a turn offers 2 to 7 options and they differ every time, so the model stores which actions were legal in `S'` and the max is taken over those. Maximising over unavailable actions would leak value from moves that cannot be played.

2. The model is deterministic, but the game is not. The book's Dyna-Q assumes a deterministic environment and keeps one `(R, S')` per pair. Battles roll damage, so the same `(S, A)` can lead elsewhere. This code keeps the book's assumption deliberately because the deterministic model is the simplest thing that works, and the compressed state hides much of the variation. The deterministic assumption is also the first thing to revisit if learning plateaus, either through stochastic Dyna-Q with outcome counts, or through Dyna-Q+ (section 8.3).

## Running it

```bash
# train (about 15 minutes for 50 episodes)
uv run python -m experiments.dyna-q.train --episodes 50

# how good is it? the official benchmark, straight from this folder
uv run pokelike bot bench --bot bots/dyna-q --dry-run
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

The `--fixed-seed` flag is the sanity check worth running first, because on a single repeated run the agent should get visibly better within a few dozen episodes. If the agent does not improve, the bug is in the encoding or the reward rather than in the hyperparameters.

## Where to look when tuning

The `--planning-steps` flag is the cheap knob. Planning steps cost no browser time. Raising the value to 50 is nearly free in wall clock. Diminishing returns come from the model being wrong (see departure 2) rather than from cost.

The encoding matters more than the hyperparameters. The `env/encoding.py` file decides what the agent can even distinguish. If two situations that need different moves collapse into the same key, no amount of `alpha` will fix the problem.

The `gamma` value of 0.95, over episodes lasting 15 to 35 steps, means the +500 for finishing is discounted to roughly 500 × 0.95³⁰ ≈ 107 at the start of a run. Since almost no early run finishes, that term does very little in practice, and the learning signal that actually drives improvement is +50 per map cleared.

## Results so far

The agent was trained on 90 episodes (n=30 planning steps, 22 minutes, 569 states discovered, 46159 Q updates) and then benchmarked on the 50 standard seeds against the random baseline. Both played the same seeds, so the comparison is paired.

```
                score~  stdev   worst   best   steps~  faints~
dyna-q v1          4.9   26.8     -70     85     29.7      3.0
random            -3.5   20.9     -55     65     17.1      4.1

paired difference: +8.4 per seed, t = 1.70
wins 24, draws 6, losses 20
```

Read this honestly. The t-statistic of 1.70 is not significant, because with 50 seeds and this much variance, +8.4 points could be luck. Winning 24 of 50 is barely a coin flip.

But two numbers are unambiguous. The agent survives 74% longer (29.7 steps against 17.1) and loses a quarter fewer Pokemon (3.0 faints against 4.1). The agent clearly learned the part of the reward it was hit with most often, which is -10 every time something faints.

What the agent did not learn is to make progress. The `maps cleared` metric is 0 for both, and that metric is where the +50s live. So the policy is currently a good survivor and a bad climber, which makes sense because staying alive is rewarded locally and constantly, while clearing a map is a long chain of decisions ending in a single payout that 90 episodes almost never reached.

That is the thing to attack next, and the problem points at the algorithm rather than the hyperparameters, because sparse delayed reward is what n-step methods (Chapter 7) and prioritised sweeping (8.4) are for.

## Then it was given more, and it got worse

That last paragraph turned out to be wrong, and the record is left standing rather than edited after the fact.

Version 2 of the encoding fixed the fragmentation described above (563 states holding 686 pairs became 397 holding 940). The agent then trained for 400 episodes with 50 planning steps, producing 465k updates. The agent was evaluated greedily on 20 held-out seeds against random play on the same seeds:

```
               mean score   wins
dyna-q v2            -3.8    6/20   (2 draws, 12 losses)
random                7.0
```

The agent lost. With more episodes and a better-conditioned table, the agent still went backwards.

The detailed log had already said why, before either evaluation:

```
    1 | starter-screen
      | [0] Bulbasaur Lv5  [1] Charmander Lv5  [2] Squirtle Lv5
      |    Q: slot0=6.3, slot1=6.2, slot2=6.3
```

The three values sit within a rounding error of each other, because the encoding shows the agent three indistinguishable slots where a player sees a Grass starter, a Fire one and a Water one with different stats. No number of episodes fixes that problem because the information never reaches the table.

So the diagnosis in the previous section, which said to attack the algorithm, was the wrong call. The limit was the representation. The [`sarsa/`](../sarsa/) experiment tests that hypothesis using the same reward, the same environment, and the same held-out protocol, but with 81 linear features instead of a table (100 since). The SARSA agent won 15 of 25 with no losses, and the trained rows it produced are near the top of the standings.

The tabular version is kept because a Q-table is the clearest thing to read when you want to know what an agent believes, and because a negative result you can reproduce is worth more than one you quietly delete.
