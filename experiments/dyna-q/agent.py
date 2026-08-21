"""TABULAR DYNA-Q

Sutton & Barto, 2nd edition, Chapter 8 "Planning and Learning with Tabular
Methods", section 8.2 "Dyna: Integrated Planning, Acting, and Learning". The
pseudocode below follows the boxed algorithm in that section step for step.

    Loop forever:
      (a) S <- current (nonterminal) state
      (b) A <- eps-greedy(S, Q)
      (c) Take action A; observe R, S'
      (d) Q(S,A) <- Q(S,A) + alpha [R + gamma max_a Q(S',a) - Q(S,A)]
      (e) Model(S,A) <- R, S'                      (assuming a deterministic env)
      (f) Loop repeat n times:
            S  <- random previously observed state
            A  <- random action previously taken in S
            R, S' <- Model(S,A)
            Q(S,A) <- Q(S,A) + alpha [R + gamma max_a Q(S',a) - Q(S,A)]

Steps (a)-(d) are plain Q-learning (section 6.5). What Dyna adds is (e) and (f):
a learned model of the environment, and n extra updates per real step drawn from
remembered experience.


WHY DYNA-Q AND NOT PLAIN Q-LEARNING HERE
----------------------------------------
Because this environment is slow. Every real step drives a browser and costs
roughly 0.7 seconds, while a planning update is a dictionary lookup and some
arithmetic. Dyna is exactly the method for that situation: it is designed to
squeeze more learning out of each expensive interaction. With n = 20 you get
twenty times the updates for the same wall-clock cost.

That is the textbook motivation for Dyna, and it happens to describe this
problem almost perfectly.


TWO DEPARTURES FROM THE BOOK, AND WHY
-------------------------------------
1. THE ACTION SET CHANGES WITH THE STATE. In the maze of section 8.2 every state
   offers the same four moves, so `max_a Q(S',a)` ranges over a fixed set. Here
   a turn offers between two and seven options and they differ every time, so
   the model has to remember which actions were legal in S' and the max is taken
   over those. Maximising over actions that are not available would leak value
   from moves that cannot be played.

2. THE MODEL IS DETERMINISTIC, THE GAME IS NOT. The book's Dyna-Q assumes a
   deterministic environment and stores one (R, S') per pair. Battles here have
   random damage rolls, so the same (S, A) can lead elsewhere. We keep the
   book's assumption on purpose — it is the simplest thing that works, and the
   compressed state hides most of the variation anyway — but it is the first
   thing to revisit if learning plateaus. The natural next step is stochastic
   Dyna-Q, storing counts per outcome, or Dyna-Q+ (section 8.3) which adds an
   exploration bonus for pairs not tried in a long time.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..env.encoding import ENCODING_VERSION  # single source of truth


class DynaQ:
    def __init__(
        self,
        alpha: float = 0.1,          # step size
        gamma: float = 0.95,         # discount
        epsilon: float = 0.2,        # exploration
        epsilon_min: float = 0.02,
        epsilon_decay: float = 0.995,
        planning_steps: int = 20,    # the n of the algorithm box
        optimistic: float = 0.0,     # initial Q, > 0 encourages early exploration
        seed: int = 0,
    ) -> None:
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.planning_steps = planning_steps
        self.optimistic = optimistic
        self.rng = random.Random(seed)

        # Q[state][action] -> value. A dict of dicts rather than a dense tensor,
        # because both dimensions are sparse and string-keyed (see features.py).
        self.Q: dict[tuple, dict[str, float]] = defaultdict(dict)

        # Model[(state, action)] -> (reward, next_state, legal actions in next_state)
        self.model: dict[tuple, tuple[float, tuple, list[str]]] = {}

        self.updates = 0

    # --------------------------------------------------------------- policy

    def value(self, state: tuple, action: str) -> float:
        return self.Q[state].get(action, self.optimistic)

    def best_action(self, state: tuple, actions: list[str]) -> str:
        """Greedy pick, ties broken at random so the first key is not privileged."""
        best = max(self.value(state, a) for a in actions)
        return self.rng.choice([a for a in actions if self.value(state, a) == best])

    def act(self, state: tuple, actions: list[str], greedy: bool = False) -> str:
        """eps-greedy action selection (Sutton & Barto, section 2.2)."""
        if not greedy and self.rng.random() < self.epsilon:
            return self.rng.choice(actions)
        return self.best_action(state, actions)

    # ---------------------------------------------------------------- learning

    def _q_update(self, s: tuple, a: str, r: float, s2: tuple, legal2: list[str]) -> None:
        """One Q-learning backup: step (d) of the algorithm box.

        `legal2` is empty at a terminal state, and then the bootstrap term is
        zero, which is what makes the return finite at the end of an episode.
        """
        best_next = max((self.value(s2, x) for x in legal2), default=0.0)
        target = r + self.gamma * best_next
        self.Q[s][a] = self.value(s, a) + self.alpha * (target - self.value(s, a))
        self.updates += 1

    def observe(self, s: tuple, a: str, r: float, s2: tuple, legal2: list[str]) -> None:
        """A real transition: steps (d) and (e)."""
        self._q_update(s, a, r, s2, legal2)
        self.model[(s, a)] = (r, s2, list(legal2))

    def plan(self) -> None:
        """Step (f): n updates from remembered experience.

        This costs no interaction with the game at all, which is the entire
        point of Dyna in a slow environment.
        """
        if not self.model:
            return
        keys = list(self.model)
        for _ in range(self.planning_steps):
            s, a = self.rng.choice(keys)
            r, s2, legal2 = self.model[(s, a)]
            self._q_update(s, a, r, s2, legal2)

    def end_episode(self) -> None:
        """Anneal exploration. Early on we want breadth, later we want the greedy
        policy to actually be followed and refined."""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    # ------------------------------------------------------------ persistence

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "encoding_version": ENCODING_VERSION,
            "hyperparameters": {
                "alpha": self.alpha, "gamma": self.gamma,
                "epsilon": self.epsilon, "planning_steps": self.planning_steps,
                "optimistic": self.optimistic,
            },
            "updates": self.updates,
            # JSON has no tuple keys, so states are serialised as strings and
            # read back with literal_eval on load.
            "Q": {repr(s): v for s, v in self.Q.items() if v},
        }, indent=1), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path, **kwargs: Any) -> "DynaQ":
        from ast import literal_eval

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("encoding_version") != ENCODING_VERSION:
            raise ValueError(
                f"the table was trained with encoding version "
                f"{data.get('encoding_version')}, this code is version "
                f"{ENCODING_VERSION}. features.py changed, so the states no "
                f"longer mean the same thing: retrain."
            )
        agent = cls(**kwargs)
        for s, values in data["Q"].items():
            agent.Q[literal_eval(s)] = dict(values)
        agent.updates = data.get("updates", 0)
        return agent

    # ------------------------------------------------------------------ stats

    def summary(self) -> dict[str, Any]:
        return {
            "states": len(self.Q),
            "state_action_pairs": sum(len(v) for v in self.Q.values()),
            "model_entries": len(self.model),
            "updates": self.updates,
            "epsilon": round(self.epsilon, 4),
        }
