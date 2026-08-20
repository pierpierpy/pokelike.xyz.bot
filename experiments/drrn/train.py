"""Fit the network to a collected dataset. No browser, no episodes, just data.

    uv run --with numpy python -m experiments.drrn.train --data mixed --iters 30

Fitted Q iteration (Ernst, Geurts & Wehenkel, JMLR 2005): treat improving the
policy as a sequence of ordinary regressions. Round k builds a target for every
transition out of the PREVIOUS round's network,

    y = r + γ · max_a' Q_{k-1}(x')

and fits Q_k to it. The max is over the actions that were actually available at
the next decision point, which is why collection records all of them.

Why this rather than online SARSA with a browser attached: the data is the
expensive part and it is already on disk, so a round is arithmetic over a fixed
array and takes seconds. Twenty rounds of policy improvement cost less than one
episode of play. It also removes the step-size tuning that a bootstrapped online
method needs — each round is a supervised fit, which either converges or does
not, visibly.

THE NETWORK IS RE-INITIALISED EVERY FEW ROUNDS
Reusing one dataset for many rounds overfits the network to what it saw first,
and more reuse makes it worse rather than better — the primacy bias
(Nikishin et al., arXiv:2205.07802). Throwing the weights away while keeping the
data is what makes the reuse safe. The targets survive a reset because they live
in the dataset, not in the weights.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from experiments.env.logs import tee
from experiments.sarsa.features import FeatureSet

from .agent import QNet

HERE = Path(__file__).parent
DATA = HERE / "output" / "data"
MODELS = HERE / "output" / "models"
RUNS = HERE / "output" / "runs"


def unflat(pairs: list[float], n: int, out: np.ndarray) -> None:
    """Write a flat [i, v, i, v, …] row into a preallocated dense row."""
    for k in range(0, len(pairs), 2):
        out[int(pairs[k])] = pairs[k + 1]


def load(tag: str, n_features: int) -> dict:
    """Every shard matching `tag` as flat arrays, plus the ragged next-action index."""
    shards = sorted(DATA.glob(f"{tag}*.jsonl"))
    if not shards:
        raise SystemExit(
            f"no data for '{tag}' in {DATA}\n"
            f"Collect some first:  uv run --with numpy python -m "
            f"experiments.drrn.collect --episodes 400 --workers 8"
        )

    xs, rs, nexts, episodes = [], [], [], []
    for shard in shards:
        with shard.open(encoding="utf-8") as fh:
            for line in fh:
                ep = json.loads(line)
                episodes.append({k: ep[k] for k in ("seed", "greedy", "badges", "steps")})
                for x, r, nx in ep["t"]:
                    xs.append(x)
                    rs.append(r)
                    nexts.append(nx)

    n = len(xs)
    X = np.zeros((n, n_features), dtype=np.float32)
    for i, row in enumerate(xs):
        unflat(row, n_features, X[i])

    # The next-action features of every transition in one array, with a slice
    # per transition. Ragged rows cannot be an array, and a list of arrays makes
    # the forward pass n small calls instead of one large one.
    counts = np.array([len(nx) for nx in nexts], dtype=np.int64)
    offsets = np.concatenate([[0], np.cumsum(counts)])
    Xn = np.zeros((int(counts.sum()), n_features), dtype=np.float32)
    k = 0
    for nx in nexts:
        for row in nx:
            unflat(row, n_features, Xn[k])
            k += 1

    return {
        "X": X, "r": np.array(rs, dtype=np.float32),
        "Xn": Xn, "offsets": offsets, "counts": counts,
        "episodes": episodes, "shards": [s.name for s in shards],
    }


def max_next(net: QNet, Xn: np.ndarray, offsets: np.ndarray,
             counts: np.ndarray) -> np.ndarray:
    """max_a' Q(x') per transition; 0 where the episode ended."""
    out = np.zeros(len(counts), dtype=np.float32)
    if len(Xn) == 0:
        return out
    q = net.forward(Xn.astype(np.float64)).astype(np.float32)
    # np.maximum.reduceat over the slices, skipping the empty ones: reduceat
    # given an empty slice returns the element at the offset, which would be
    # another transition's value.
    live = counts > 0
    starts = offsets[:-1][live]
    out[live] = np.maximum.reduceat(q, starts)
    return out


def train(tag: str = "mixed", iters: int = 30, gamma: float = 0.98,
          hidden: tuple[int, ...] = (64, 64), lr: float = 1e-3,
          epochs: int = 6, batch: int = 512, reset_every: int = 10,
          seed: int = 0, out: str = "drrn.json") -> dict:
    fs = FeatureSet()
    d = load(tag, fs.n)
    X, r = d["X"], d["r"]
    eps = d["episodes"]
    print(f"{len(X)} transitions from {len(eps)} episodes in {len(d['shards'])} shards")
    print(f"  behaviour: {sum(e['greedy'] for e in eps)} guided, "
          f"{sum(not e['greedy'] for e in eps)} random, "
          f"{np.mean([e['badges'] for e in eps]):.2f} badges mean")
    print(f"  next-action rows: {len(d['Xn'])}, terminal transitions: {int((d['counts'] == 0).sum())}")

    net = QNet(fs.n, hidden, lr=lr, seed=seed)
    Xd = X.astype(np.float64)
    history = []
    started = time.monotonic()

    for k in range(iters):
        # Targets from the PREVIOUS round's network, before any reset: they are
        # what carries the policy improvement forward, not the weights.
        y = r + gamma * max_next(net, d["Xn"], d["offsets"], d["counts"])
        if reset_every and k and k % reset_every == 0:
            net.reinit(seed_offset=k)
            print(f"  [{k:>3}] network re-initialised")
        loss = net.fit(Xd, y.astype(np.float64), epochs=epochs, batch=batch)
        q = net.forward(Xd)
        row = {"iter": k, "loss": round(float(loss), 5),
               "q_mean": round(float(q.mean()), 3),
               "q_max": round(float(q.max()), 3),
               "target_mean": round(float(y.mean()), 3)}
        history.append(row)
        print(f"  [{k:>3}] loss {row['loss']:>10.4f}   q~ {row['q_mean']:>8.3f}   "
              f"q+ {row['q_max']:>9.3f}   target~ {row['target_mean']:>8.3f}")
        if not np.isfinite(loss):
            print("  diverged: stopping. Lower --lr, or shorten --epochs.")
            break

    MODELS.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    path = net.save(MODELS / out, extra={
        "feature_groups": fs.groups,
        "encoding_version": 2,
        "algorithm": "fitted Q iteration, MLP on x(s,a)",
        "hyperparameters": {"gamma": gamma, "lr": lr, "iters": iters,
                            "epochs": epochs, "reset_every": reset_every},
        "transitions": len(X),
        "episodes": len(eps),
    })
    (RUNS / (Path(out).stem + "_history.json")).write_text(
        json.dumps(history, indent=1), encoding="utf-8")
    print(f"\n{(time.monotonic() - started) / 60:.1f} min")
    print(f"model:   {path}")
    print(f"\nMeasure it the one way there is:")
    print(f"  uv run pokelike bot bench --bot experiments/drrn --dry-run")
    return {"history": history, "path": path}


def parse_hidden(spec: str) -> tuple[int, ...]:
    """Layer sizes, or `()` for no hidden layer at all.

    The empty case is the control arm and the reason this is a function. Fitting
    q̂ = wᵀx by the SAME fitted Q iteration on the SAME shards is what separates
    the three things that otherwise move together here: the shape of q̂, the
    algorithm, and the data distribution. Compared only against the online
    SARSA(λ) number, a result cannot say which of them it is about.
    """
    spec = (spec or "").strip().lower()
    if spec in ("", "none", "linear"):
        return ()
    return tuple(int(h) for h in spec.split(","))


def main() -> int:
    p = argparse.ArgumentParser(description="Fit Q offline on collected transitions.")
    p.add_argument("--data", default="mixed", help="shard prefix under output/data/")
    p.add_argument("--iters", type=int, default=30, help="fitted Q rounds")
    p.add_argument("--gamma", type=float, default=0.98)
    p.add_argument("--hidden", default="64,64",
                   help="layer sizes, comma separated. '' or 'linear' fits q = wx "
                        "with no hidden layer: the control arm")
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--epochs", type=int, default=6, help="passes per round")
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--reset-every", type=int, default=10,
                   help="re-initialise the network every N rounds; 0 disables")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="drrn.json")
    a = p.parse_args()
    with tee(HERE, a.out.replace(".json", "")) as path:
        train(a.data, a.iters, a.gamma, parse_hidden(a.hidden),
              a.lr, a.epochs, a.batch, a.reset_every, a.seed, a.out)
        print(f"log:     {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
