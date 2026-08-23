"""The smallest complete experiment, showing the structure of propose, measure, keep, save.

    uv run python -m experiments.example.train --episodes 20

This experiment is deliberately simple. Its purpose is the structure: every
experiment in this project is this loop with something better in the middle.

    1. play episodes against the environment in `env/`
    2. score them with a reward from `env/rewards.py`
    3. change the thing being learned
    4. save it somewhere a bot can load

The learned model is one number per node kind, representing how much that kind
of node seems to be worth. The approach is tabular with one row and no state at
all, which is why it will not beat much, and why the interesting question in this
game turned out to be what the agent gets to see rather than how it updates. See
../README.md.

Your own experiments are yours. The `experiments/` directory is gitignored apart
from this example and the shared `env/`, so nothing you try here ends up in a
pull request by accident.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

from experiments.env.logs import tee
from experiments.env.rewards import get as get_reward
from pokelike import session

HERE = Path(__file__).parent
OUT = HERE / "output"

NODE_KINDS = ["catch", "battle", "trainer", "item", "pokecenter", "question",
              "move_tutor", "trade", "boss", "pokemart", "shiny"]


def act(values: dict[str, float], state: dict, rng: random.Random,
           epsilon: float) -> int:
    """Selects an action epsilon-greedy over the value of each action's node kind."""
    actions = state["actions"]
    if rng.random() < epsilon:
        return rng.randrange(len(actions))
    scored = [values.get(a.get("node") or "", 0.0) for a in actions]
    best = max(scored)
    return rng.choice([i for i, v in enumerate(scored) if v == best])


def train(episodes: int = 20, seed0: int = 1, reward: str = "progress",
          alpha: float = 0.1, epsilon: float = 0.3, max_steps: int = 300) -> dict:
    from tqdm import tqdm

    reward_fn = get_reward(reward)
    values = {k: 0.0 for k in NODE_KINDS}
    rng = random.Random(seed0)
    history = []

    with session() as game:
        bar = tqdm(range(episodes), desc="example", unit="ep")
        for ep in bar:
            seed = seed0 + ep
            obs = game.reset(seed=seed)
            taken, total = [], 0.0

            while not obs.get("done") and obs.get("actions") and game.steps < max_steps:
                i = choose(values, obs, rng, epsilon)
                kind = (obs["actions"][i] or {}).get("node")
                before = obs
                obs = game.step(i)
                done = bool(obs.get("done")) or not obs.get("actions")
                # At game over the engine wipes `state`, so score against the
                # last live snapshot or every run ends with a phantom collapse.
                after = obs if obs.get("run") else (game.last_alive or before)
                r = reward_fn(before, after, done, obs.get("screen") == "win-screen")
                total += r
                if kind:
                    taken.append(kind)

            # Every node kind taken this episode moves toward the run's total.
            # This is crude on purpose, with no discounting, no credit
            # assignment, and no state.
            for kind in set(taken):
                values[kind] += alpha * (total - values[kind])

            alive = game.last_alive or {}
            history.append({"episode": ep, "seed": seed, "reward": round(total, 1),
                            "badges": (alive.get("run") or {}).get("badges", 0)})
            bar.set_postfix(badges=round(statistics.mean(
                h["badges"] for h in history[-10:]), 2))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "values.json"
    path.write_text(json.dumps({"values": values, "episodes": episodes,
                                "reward": reward}, indent=1), encoding="utf-8")

    print("\nwhat it decided each node kind is worth:")
    for k, v in sorted(values.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<12}{v:>9.1f}")
    print(f"\nsaved to {path}")
    return {"values": values, "history": history}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--episodes", type=int, default=20)
    p.add_argument("--seed0", type=int, default=1)
    p.add_argument("--reward", default="progress")
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--epsilon", type=float, default=0.3)
    a = p.parse_args()
    with tee(HERE, "train"):
        train(episodes=a.episodes, seed0=a.seed0, reward=a.reward,
              alpha=a.alpha, epsilon=a.epsilon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
