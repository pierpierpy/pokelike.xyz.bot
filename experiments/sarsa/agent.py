"""Semi-gradient SARSA(λ) with linear function approximation.

Sutton & Barto, 2nd edition: chapter 10 "On-policy Control with
Approximation" for the semi-gradient control update, and chapter 12
"Eligibility Traces", section 12.7, for the SARSA(λ) form used here.

    q̂(s, a, w) = wᵀ x(s, a)

    Loop for each episode:
      z <- 0
      S, A <- initial state and action, A from eps-greedy on q̂
      Loop for each step:
        Take A, observe R, S'
        δ <- R - q̂(S,A,w)
        z <- γλz + x(S,A)                       (accumulating traces)
        If S' terminal:  w <- w + αδz ; go to next episode
        A' <- eps-greedy(S', q̂)
        δ <- δ + γ q̂(S',A',w)
        w <- w + αδz
        S, A <- S', A'


Why linear function approximation over a table
-----------------------------------------------
Two problems with the tabular agent, neither fixed by training longer.

The tabular agent cannot see. The state is six numbers and actions are keyed by
type, so on the starter screen the table learns 6.3 / 6.2 / 6.3, three
indistinguishable slots where a player sees Bulbasaur, Charmander and Squirtle.
No amount of extra episodes fixes that, because the information never reaches the
table.

The tabular agent cannot generalise. Every table cell is learned alone, and each
real step costs 0.7 seconds of browser. Sharing weights across states is the
difference between needing thousands of episodes and needing hundreds.

Traces address the third problem. Badges arrive many decisions after the choices
that earned them, and a one-step backup moves credit one step per visit. λ = 0.9
spreads credit down the whole chain immediately.


The part that needs care
------------------------
Linear FA with a bootstrapped target can diverge, which tabular methods cannot
(chapter 11, "the deadly triad" of approximation, bootstrapping, and off-policy).
SARSA is on-policy, which removes one leg, but the step size still matters. The
step size is normalised by the number of active features so that adding features
does not silently multiply the effective learning rate, a mistake that looks like
the algorithm being unstable when the tuning is the real problem.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .features import ALL_GROUPS, FeatureSet

# Version 2 added the team-order decision and the features that describe it, so
# a v1 weight vector indexes a different space. A mismatch is refused on load
# rather than zero-filled, because silently reading old weights under a new
# feature set produces a policy nobody trained.
ENCODING_VERSION = 2


class SarsaLambda:
    def __init__(
        self,
        alpha: float = 0.05,        # step size, per active feature
        gamma: float = 0.98,        # discount
        lam: float = 0.9,           # trace decay
        epsilon: float = 0.3,
        epsilon_min: float = 0.02,
        epsilon_decay: float = 0.99,
        seed: int = 0,
        featureset: FeatureSet | None = None,
        alpha_norm: float | None = None,
    ) -> None:
        # What to divide the step size by. None means "the number of features
        # active right now", which is the sane default for a single run but is
        # wrong for comparing feature sets because fewer groups means fewer
        # active features means a larger step per feature. An ablation that drops
        # a group also raises the learning rate and answers a different question.
        #
        # Measured on this game, the full set activates 9.0 features per (s, a),
        # action-only activates 3.0, and minimal activates 1.2, a 7.5x spread.
        # The first ablation duly diverged in exactly that order.
        self.alpha_norm = alpha_norm
        # This parameter controls which feature vector the agent speaks. The
        # default is the full set, so nothing that existed before this parameter
        # changes behaviour.
        self.fs = featureset or FeatureSet()
        self.alpha = alpha
        self.gamma = gamma
        self.lam = lam
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.rng = random.Random(seed)

        self.w = [0.0] * self.fs.n
        self.z = [0.0] * self.fs.n
        self.updates = 0

    # ------------------------------------------------------------------ value

    def q(self, x: dict[int, float]) -> float:
        return sum(self.w[i] * v for i, v in x.items())

    def all_features(self, state: dict[str, Any],
                     actions: list[dict] | None = None) -> list[dict[int, float]]:
        return [self.fs.of(state, a) for a in (state["actions"] if actions is None else actions)]

    # ----------------------------------------------------------------- policy

    def act(self, state: dict[str, Any], greedy: bool = False,
               actions: list[dict] | None = None) -> int:
        """Index of the chosen action, over `state["actions"]` or an explicit list.

        The explicit list is what makes team order learnable with the same q̂
        because reordering is a decision the game does not put in `actions`, so
        its options are built separately and scored by the very same weights.
        """
        xs = self.all_features(state, actions)
        if not greedy and self.rng.random() < self.epsilon:
            return self.rng.randrange(len(xs))
        values = [self.q(x) for x in xs]
        best = max(values)
        return self.rng.choice([i for i, v in enumerate(values) if v == best])

    # --------------------------------------------------------------- learning

    def start_episode(self) -> None:
        self.z = [0.0] * self.fs.n

    def update(
        self,
        x: dict[int, float],
        reward: float,
        x_next: dict[int, float] | None,
    ) -> None:
        """One SARSA(λ) step. `x_next` is None at a terminal state."""
        delta = reward - self.q(x)

        # z <- γλz + x(S,A), accumulating traces.
        decay = self.gamma * self.lam
        for i in range(self.fs.n):
            self.z[i] *= decay
        for i, v in x.items():
            self.z[i] += v

        if x_next is not None:
            delta += self.gamma * self.q(x_next)

        # The step is normalised so the effective rate is stable as features are
        # added or removed. The `alpha_norm` parameter pins the divisor to a
        # constant shared across variants, which is what makes an ablation vary
        # one thing.
        step = self.alpha / (self.alpha_norm or max(1, len(x)))
        for i in range(self.fs.n):
            if self.z[i]:
                self.w[i] += step * delta * self.z[i]
        self.updates += 1

    def end_episode(self) -> None:
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    # ------------------------------------------------------------ persistence

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "encoding_version": ENCODING_VERSION,
            # The groups travel with the weights. Weights are stored by name, so
            # loading them into a different set would zero-fill what is missing
            # and hand back a policy nobody ever trained.
            "feature_groups": self.fs.groups,
            "algorithm": "semi-gradient SARSA(lambda), linear (S&B ch. 10 and 12.7)",
            "hyperparameters": {
                "alpha": self.alpha, "gamma": self.gamma, "lambda": self.lam,
                "epsilon": self.epsilon, "alpha_norm": self.alpha_norm,
            },
            "updates": self.updates,
            # Weights are stored by name so the learned policy can be read
            # rather than only run.
            "weights": dict(zip(self.fs.names, [round(v, 4) for v in self.w])),
        }, indent=1), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path, **kwargs: Any) -> "SarsaLambda":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("encoding_version") != ENCODING_VERSION:
            raise ValueError(
                f"weights were trained with feature set v{data.get('encoding_version')}, "
                f"this code is v{ENCODING_VERSION}: the vector no longer means the "
                f"same thing, so retrain."
            )
        kwargs.setdefault("featureset", FeatureSet(data.get("feature_groups")))
        agent = cls(**kwargs)
        stored = data["weights"]
        missing = [n for n in agent.fs.names if n not in stored]
        if missing:
            raise ValueError(
                f"the saved weights are missing {len(missing)} of this feature set's "
                f"names (first: {missing[:3]}). Zero-filling them would invent a "
                f"policy that was never trained, so this refuses instead."
            )
        agent.w = [float(stored[n]) for n in agent.fs.names]
        agent.updates = data.get("updates", 0)
        return agent

    # ------------------------------------------------------------------ stats

    def summary(self) -> dict[str, Any]:
        live = [(n, v) for n, v in zip(self.fs.names, self.w) if abs(v) > 1e-6]
        return {
            "features": self.fs.n,
            "groups": "+".join(self.fs.groups),
            "alpha_norm": self.alpha_norm,
            "nonzero_weights": len(live),
            "updates": self.updates,
            "epsilon": round(self.epsilon, 4),
        }

    def top_weights(self, n: int = 12) -> list[tuple[str, float]]:
        """The features it leaned on hardest, positive and negative.

        The point of a linear model is that you can read what it learned.
        """
        pairs = [(name, w) for name, w in zip(self.fs.names, self.w)]
        pairs.sort(key=lambda p: -abs(p[1]))
        return [(n_, round(w, 3)) for n_, w in pairs[:n]]
