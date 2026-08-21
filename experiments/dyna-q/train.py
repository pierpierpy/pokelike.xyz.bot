"""Training loop for Dyna-Q.

    uv run python -m experiments.dyna-q.train --episodes 200

Each episode is one run of the game, from the starter to game over. The loop is
the algorithm box of Sutton & Barto section 8.2, with the planning phase run
after every real step.

Episodes are seeded consecutively rather than repeated, so the agent sees many
different maps and learns something general instead of memorising one layout.
Pass --fixed-seed to do the opposite and watch it overfit a single run, which is
a useful sanity check that learning happens at all.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from experiments.env.logs import tee
from experiments.env.environment import TrainingEnv

from .agent import DynaQ

HERE = Path(__file__).parent
OUT = HERE / "output"
MODELS = OUT / "models"
RUNS = OUT / "runs"


def train(
    episodes: int = 200,
    seed0: int = 1,
    fixed_seed: bool = False,
    planning_steps: int = 20,
    alpha: float = 0.1,
    gamma: float = 0.95,
    epsilon: float = 0.3,
    optimistic: float = 0.0,
    port: int = 8600,
    reward: str = "progress",
    out: str = "q_table.json",
    log_every: int = 10,
) -> dict:
    agent = DynaQ(alpha=alpha, gamma=gamma, epsilon=epsilon,
                  planning_steps=planning_steps, optimistic=optimistic, seed=seed0)

    history: list[dict] = []
    started = time.monotonic()

    from tqdm import tqdm

    with TrainingEnv(port=port, reward=reward) as env:
        bar = tqdm(range(episodes), desc="dyna-q", unit="ep")
        for ep in bar:
            seed = seed0 if fixed_seed else seed0 + ep
            s, actions = env.reset(seed=seed)

            total_reward = 0.0
            steps = 0
            while actions:
                a = agent.act(s, actions)
                s2, actions2, r, done = env.step(a)

                agent.observe(s, a, r, s2, actions2)   # steps (d) and (e)
                agent.plan()                           # step (f)

                total_reward += r
                steps += 1
                s, actions = s2, actions2
                if done:
                    break

            agent.end_episode()
            score = env.score() or {}
            alive = env.game.last_alive or {}
            row = {
                "episode": ep,
                "seed": seed,
                "steps": steps,
                "reward": round(total_reward, 1),
                # Badges are the metric that matters; total reward per episode
                # conflates playing well with surviving long, so a curve drawn
                # from reward alone can mislead in either direction.
                "badges": (alive.get("run") or {}).get("badges", 0),
                "score": score.get("points_no_time"),
                "ending": (env.observation or {}).get("screen"),
                "epsilon": round(agent.epsilon, 4),
                "states": len(agent.Q),
            }
            history.append(row)

            window = history[-log_every:]
            bar.set_postfix(
                badges=round(sum(h["badges"] for h in window) / len(window), 2),
                reward=round(sum(h["reward"] for h in window) / len(window), 1),
                eps=round(agent.epsilon, 3),
                states=row["states"],
            )

    elapsed = time.monotonic() - started
    table = agent.save(MODELS / out)

    RUNS.mkdir(parents=True, exist_ok=True)
    log = RUNS / (Path(out).stem + "_history.json")
    log.write_text(json.dumps(history, indent=1), encoding="utf-8")

    print(f"\ntrained on {episodes} episodes with reward '{reward}' "
          f"in {elapsed / 60:.1f} min")
    print(f"agent: {agent.summary()}")
    print(f"table: {table}")
    print(f"history: {log}")
    return {"agent": agent.summary(), "history": history, "table": str(table)}


def main() -> int:
    p = argparse.ArgumentParser(description="Train a Dyna-Q agent on pokelike.")
    p.add_argument("--episodes", type=int, default=200)
    p.add_argument("--seed0", type=int, default=1, help="seed of the first episode")
    p.add_argument("--fixed-seed", action="store_true",
                   help="replay the same run every episode (overfitting check)")
    p.add_argument("--planning-steps", type=int, default=20, help="the n of Dyna-Q")
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--gamma", type=float, default=0.95)
    p.add_argument("--epsilon", type=float, default=0.3)
    p.add_argument("--optimistic", type=float, default=0.0,
                   help="initial Q value; > 0 encourages early exploration")
    p.add_argument("--port", type=int, default=8600)
    p.add_argument("--reward", default="progress",
                   help="which reward function (see experiments/common/rewards.py)")
    p.add_argument("--out", default="q_table.json")
    p.add_argument("--log-every", type=int, default=10)
    a = p.parse_args()

    train(episodes=a.episodes, seed0=a.seed0, fixed_seed=a.fixed_seed,
          planning_steps=a.planning_steps, alpha=a.alpha, gamma=a.gamma,
          epsilon=a.epsilon, optimistic=a.optimistic, port=a.port, reward=a.reward, out=a.out,
          log_every=a.log_every)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
