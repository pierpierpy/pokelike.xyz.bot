"""The one change under test: a network where the SARSA experiment has a dot product.

    q̂(s, a) = MLP(x(s, a))          instead of        q̂(s, a) = wᵀ x(s, a)

The features and the actions-are-scored-one-at-a-time interface are the same. The
network is run once per candidate action and the best score wins, which is what
makes the approach work with an action set that changes every turn, the
architecture text-game agents use for the same reason (He et al., "Deep
Reinforcement Learning with a Natural Language Action Space", arXiv:1511.04636).

Why a network at all, given the linear model plateaued:

The weights the linear model learns have most of their mass on features that are
identical across every action in a state, such as `team_size`, `bias`, and
`map_index`. Those features cancel in the argmax and cannot change a choice.
Deleting them does not help either (measured, 1.36 against 1.38, which is
nothing).

Those features are terms that only mean something crossed with the action. How
much a trainer node is worth depends on how small the team is. The linear model
can only carry such a cross if someone writes it by hand, and three are written
by hand today. A hidden layer builds them from the same inputs without anyone
choosing which.

That is the whole hypothesis. If the hypothesis is wrong, the features are the
ceiling and no amount of capacity on top of them helps.

This module uses numpy only, so `uv run --with numpy` runs it without touching
the project environment. The trained net exports to JSON and a bot does the
forward pass in plain Python, so a submission never needs numpy installed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

# Bumped when the architecture changes meaning (layer sizes, activation, how
# the input is built). Exported weights carry this version and loading a
# mismatch is refused, because a matrix of numbers is only a policy under the
# shape that produced it.
ARCH_VERSION = 1


class QNet:
    """An MLP scoring one (state, action) pair, trained by fitted Q iteration.

    Uses Adam, ReLU, and He initialisation. The network is small on purpose
    because the input is 100 hand-built features, so the hidden layers cross
    them rather than discover them.
    """

    def __init__(self, n_in: int, hidden: tuple[int, ...] = (64, 64),
                 lr: float = 1e-3, seed: int = 0) -> None:
        self.n_in = n_in
        self.hidden = tuple(hidden)
        self.lr = lr
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.steps = 0
        self._init_params()

    def _init_params(self) -> None:
        sizes = (self.n_in, *self.hidden, 1)
        self.W = [self.rng.normal(0, math.sqrt(2.0 / a), (a, b))
                  for a, b in zip(sizes, sizes[1:])]
        self.b = [np.zeros(b) for b in sizes[1:]]
        # Adam moments, reset with the parameters they belong to.
        self.mW = [np.zeros_like(w) for w in self.W]
        self.vW = [np.zeros_like(w) for w in self.W]
        self.mb = [np.zeros_like(x) for x in self.b]
        self.vb = [np.zeros_like(x) for x in self.b]
        self.t = 0

    def reinit(self, seed_offset: int = 1) -> None:
        """Throw the weights away and start again, keeping the data.

        Reusing a fixed dataset many times overfits a network to whatever it saw
        first, and the more you reuse it the worse that gets (the primacy bias,
        Nikishin et al., arXiv:2205.07802). Periodically re-initialising while
        keeping the replay data is what buys the high reuse ratio this budget
        depends on, because there are only so many transitions, and each has to
        be worth more than one gradient step.
        """
        self.rng = np.random.default_rng(self.seed + seed_offset * 10_000)
        self._init_params()

    # ------------------------------------------------------------- inference

    def forward(self, X: np.ndarray) -> np.ndarray:
        """Q for a batch of (state, action) rows. Returns shape (n,)."""
        h = X
        for i, (w, b) in enumerate(zip(self.W, self.b)):
            h = h @ w + b
            if i < len(self.W) - 1:
                h = np.maximum(h, 0.0)
            self._cache = None
        return h[:, 0]

    def _forward_cached(self, X: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
        acts = [X]
        h = X
        for i, (w, b) in enumerate(zip(self.W, self.b)):
            h = h @ w + b
            if i < len(self.W) - 1:
                h = np.maximum(h, 0.0)
                acts.append(h)
        return h[:, 0], acts

    # -------------------------------------------------------------- learning

    def fit_batch(self, X: np.ndarray, y: np.ndarray) -> float:
        """One Adam step on the squared error against `y`. Returns the loss."""
        n = len(X)
        pred, acts = self._forward_cached(X)
        err = pred - y
        loss = float(np.mean(err ** 2))

        # dL/dpred, as a column so it multiplies through the layers.
        g = (2.0 * err / n)[:, None]
        gW: list[np.ndarray] = [None] * len(self.W)  # type: ignore[list-item]
        gb: list[np.ndarray] = [None] * len(self.b)  # type: ignore[list-item]
        for i in range(len(self.W) - 1, -1, -1):
            gW[i] = acts[i].T @ g
            gb[i] = g.sum(axis=0)
            if i > 0:
                g = (g @ self.W[i].T) * (acts[i] > 0)

        self.t += 1
        b1, b2, eps = 0.9, 0.999, 1e-8
        c1 = 1 - b1 ** self.t
        c2 = 1 - b2 ** self.t
        for i in range(len(self.W)):
            self.mW[i] = b1 * self.mW[i] + (1 - b1) * gW[i]
            self.vW[i] = b2 * self.vW[i] + (1 - b2) * gW[i] ** 2
            self.W[i] -= self.lr * (self.mW[i] / c1) / (np.sqrt(self.vW[i] / c2) + eps)
            self.mb[i] = b1 * self.mb[i] + (1 - b1) * gb[i]
            self.vb[i] = b2 * self.vb[i] + (1 - b2) * gb[i] ** 2
            self.b[i] -= self.lr * (self.mb[i] / c1) / (np.sqrt(self.vb[i] / c2) + eps)
        self.steps += 1
        return loss

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 8,
            batch: int = 512) -> float:
        """Several passes over a dataset. Returns the last epoch's mean loss."""
        n = len(X)
        last = 0.0
        for _ in range(epochs):
            order = self.rng.permutation(n)
            losses = []
            for s in range(0, n, batch):
                idx = order[s:s + batch]
                losses.append(self.fit_batch(X[idx], y[idx]))
            last = float(np.mean(losses))
        return last

    # ----------------------------------------------------------------- state

    def to_dict(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "arch_version": ARCH_VERSION,
            "n_in": self.n_in,
            "hidden": list(self.hidden),
            "W": [w.tolist() for w in self.W],
            "b": [x.tolist() for x in self.b],
            **(extra or {}),
        }

    def save(self, path: str | Path, extra: dict[str, Any] | None = None) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(extra)), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> "QNet":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("arch_version") != ARCH_VERSION:
            raise SystemExit(
                f"{path} was written by architecture v{d.get('arch_version')}, "
                f"this is v{ARCH_VERSION}. The weights mean something else under "
                f"a different shape: retrain rather than load."
            )
        net = cls(d["n_in"], tuple(d["hidden"]))
        net.W = [np.array(w) for w in d["W"]]
        net.b = [np.array(x) for x in d["b"]]
        return net


def densify(sparse: dict[int, float] | list[float], n: int) -> np.ndarray:
    """A sparse {index: value} feature dict as a dense row."""
    if isinstance(sparse, list):
        return np.asarray(sparse, dtype=np.float64)
    out = np.zeros(n)
    for i, v in sparse.items():
        out[int(i)] = v
    return out
