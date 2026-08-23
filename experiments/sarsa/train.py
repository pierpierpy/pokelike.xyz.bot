"""Training loop for semi-gradient SARSA(λ).

    uv run python -m experiments.sarsa.train --episodes 300

Unlike the tabular experiment, this module drives `Game` directly and works on
action indices rather than action keys. The distinction matters because keying by
type collapses the five equip buttons of the equip modal into one action, so a
tabular agent cannot choose which team member to give an item to. Indices keep
the buttons apart, and the features describe each one.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from experiments.env.logs import tee
from experiments.env.rewards import get as get_reward
from pokelike.assets import AssetServer
from pokelike.core.game import Game

from .agent import SarsaLambda
from .features import FeatureSet, reorder_options

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
OUT = HERE / "output"
MODELS = OUT / "models"
RUNS = OUT / "runs"


def train(
    episodes: int = 300,
    seed0: int = 1,
    reward: str = "progress",
    alpha: float = 0.05,
    gamma: float = 0.98,
    lam: float = 0.9,
    epsilon: float = 0.3,
    max_steps: int = 300,
    port: int = 8710,
    out: str = "sarsa.json",
    groups: list[str] | None = None,
    quiet: bool = False,
    checkpoint_every: int = 10,
    resume: bool = False,
    alpha_norm: float | None = None,
) -> dict:
    from tqdm import tqdm

    reward_fn = get_reward(reward)
    fs = FeatureSet(groups)
    ckpt = MODELS / (Path(out).stem + ".checkpoint.json")
    agent = SarsaLambda(alpha=alpha, gamma=gamma, lam=lam, epsilon=epsilon, seed=seed0,
                        featureset=fs, alpha_norm=alpha_norm)
    history: list[dict] = []
    first_episode = 0
    if resume and ckpt.is_file():
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        if saved.get("feature_groups") != fs.groups:
            raise SystemExit(
                f"{ckpt.name} was trained on a different feature set "
                f"({'+'.join(saved.get('feature_groups') or [])}). Resuming would "
                f"read its weights under the wrong names: delete it or retrain."
            )
        agent.w = [float(v) for v in saved["w"]]
        agent.epsilon = saved["epsilon"]
        agent.updates = saved["updates"]
        history = saved["history"]
        first_episode = saved["episode"] + 1
        print(f"resuming {out} from episode {first_episode} "
              f"({len(history)} episodes already done)")
    started = time.monotonic()

    server = AssetServer(ROOT / "site", port=port)
    server.start()
    game = Game(url=server.url)
    game.open()
    try:
        bar = tqdm(range(first_episode, episodes), initial=first_episode,
                   total=episodes, desc=(out.replace(".json", "") or "sarsa(λ)"),
                   unit="ep", disable=quiet)
        for ep in bar:
            seed = seed0 + ep
            # Reseeded per episode so a resumed run replays exactly what an
            # uninterrupted one would. The agent's own RNG breaks ties in
            # epsilon-greedy, and the RNG is not part of the checkpoint.
            agent.rng = random.Random(seed)
            obs = game.reset(seed=seed)
            agent.start_episode()

            # Two kinds of decision alternate. Reordering the team does not
            # consume a game turn, so it is a decision point of its own with
            # reward 0, an extra state in the MDP rather than an extra action
            # in it. SARSA(lambda) then handles the credit by itself because the
            # trace carries the eventual reward back through the swap that
            # helped.
            total = 0.0
            phase = "reorder"

            def pending(o, ph):
                """Options at this decision point, or [] if there is nothing to decide."""
                return reorder_options(o) if ph == "reorder" else (o.get("actions") or [])

            def settle_phase(o, ph):
                """Skip a decision point that offers nothing. Only reorder can be empty."""
                acts = pending(o, ph)
                if not acts and ph == "reorder":
                    ph = "action"
                    acts = pending(o, ph)
                return ph, acts

            phase, acts = settle_phase(obs, phase)
            i = agent.act(obs, actions=acts)
            x = fs.of(obs, acts[i])

            while True:
                before = obs
                if phase == "reorder":
                    b = acts[i]["b"]
                    if b is not None:
                        obs = game.reorder(0, b)
                    r, done = 0.0, False        # free, no turn spent, no reward
                    phase = "action"
                else:
                    obs = game.step(i)
                    done = (bool(obs.get("done")) or game.steps >= max_steps
                            or not obs.get("actions"))
                    # At game over the engine wipes `state`, so reward against
                    # the last live snapshot or every run ends with a phantom
                    # collapse.
                    after = obs if obs.get("run") else (game.last_alive or before)
                    r = reward_fn(before, after, done, obs.get("screen") == "win-screen")
                    phase = "reorder"
                total += r

                if done:
                    agent.update(x, r, None)
                    break

                phase, acts = settle_phase(obs, phase)
                i = agent.act(obs, actions=acts)
                x_next = fs.of(obs, acts[i])
                agent.update(x, r, x_next)
                x = x_next

            agent.end_episode()
            alive = game.last_alive or {}
            score = game.score() or {}
            history.append({
                "episode": ep,
                "seed": seed,
                "steps": game.steps,
                "reward": round(total, 1),
                "badges": (alive.get("run") or {}).get("badges", 0),
                "score": score.get("points_no_time"),
                "ending": obs.get("screen"),
                "epsilon": round(agent.epsilon, 4),
            })
            # Written every few episodes, because this machine restarts and a
            # 90-minute run that has to start over is a run that never finishes.
            if checkpoint_every and (ep + 1) % checkpoint_every == 0:
                MODELS.mkdir(parents=True, exist_ok=True)
                ckpt.write_text(json.dumps({
                    "episode": ep, "feature_groups": fs.groups,
                    "epsilon": agent.epsilon, "updates": agent.updates,
                    "w": [round(v, 6) for v in agent.w], "history": history,
                }), encoding="utf-8")

            w = history[-25:]
            bar.set_postfix(
                badges=round(statistics.mean(h["badges"] for h in w), 2),
                reward=round(statistics.mean(h["reward"] for h in w), 1),
                eps=round(agent.epsilon, 3),
            )
    finally:
        game.close()
        server.stop()

    elapsed = (time.monotonic() - started) / 60
    table = agent.save(MODELS / out)
    ckpt.unlink(missing_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    log = RUNS / (Path(out).stem + "_history.json")
    log.write_text(json.dumps(history, indent=1), encoding="utf-8")

    print(f"\ntrained {episodes} episodes with reward '{reward}' in {elapsed:.1f} min")
    print(f"agent: {agent.summary()}")
    print("\nwhat it leaned on:")
    for name, weight in agent.top_weights(14):
        print(f"  {name:<26} {weight:>8}")
    print(f"\nweights: {table}\nhistory: {log}")
    return {"agent": agent.summary(), "history": history}


def main() -> int:
    p = argparse.ArgumentParser(description="Train linear SARSA(lambda) on pokelike.")
    p.add_argument("--episodes", type=int, default=300)
    p.add_argument("--seed0", type=int, default=1)
    p.add_argument("--reward", default="progress")
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--gamma", type=float, default=0.98)
    p.add_argument("--lam", type=float, default=0.9, help="trace decay")
    p.add_argument("--epsilon", type=float, default=0.3)
    p.add_argument("--port", type=int, default=8710)
    p.add_argument("--out", default="sarsa.json")
    p.add_argument("--groups", default=None,
                   help="feature groups to keep, comma separated (default: all). "
                        "See features.GROUPS — this is what an ablation varies.")
    p.add_argument("--quiet", action="store_true", help="no progress bar (parallel runs)")
    p.add_argument("--checkpoint-every", type=int, default=10,
                   help="save progress every N episodes (0 disables)")
    p.add_argument("--alpha-norm", type=float, default=None,
                   help="divide the step by this constant instead of by the number "
                        "of active features. Required to compare feature sets: see "
                        "the note in agent.py")
    p.add_argument("--resume", action="store_true",
                   help="continue from the checkpoint instead of starting over")
    a = p.parse_args()
    # Written to experiments/sarsa/logs/ by the run itself, so the log of
    # a training run is never the thing that was not kept.
    with tee(HERE, a.out.replace(".json", "")) as path:
        train(
            episodes=a.episodes, seed0=a.seed0, reward=a.reward, alpha=a.alpha,
            gamma=a.gamma, lam=a.lam, epsilon=a.epsilon, port=a.port, out=a.out,
            groups=a.groups.split(",") if a.groups else None, quiet=a.quiet,
            checkpoint_every=a.checkpoint_every, resume=a.resume,
            alpha_norm=a.alpha_norm,
        )
    print(f"log: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
