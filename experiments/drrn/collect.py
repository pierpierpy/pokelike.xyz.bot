"""Play episodes and write down every transition, for training without a browser.

    uv run --with numpy python -m experiments.drrn.collect --episodes 400 --workers 8

Collection and learning are split because they are bound by different things.
Playing is bound by the browser (half a second a step, one browser per process,
and this machine has 22 cores) while fitting a small net to a fixed dataset is
bound by arithmetic and wants one process with all the data in memory. Splitting
them turns 22 cores into 22x the data rather than 22 copies of the same run.

What a row has to carry
-----------------------
Fitted Q iteration needs `max` over the actions available at the next decision
point, so a transition is (x, r, [x'₁ ... x'ₙ]) rather than just (x, r, x').
The vector includes the features of every candidate at the following decision
point. Recording only the action that was taken would make the dataset usable
for evaluating the behaviour policy and useless for improving on it.

Both decision points are recorded, the move and the team order, exactly as the
SARSA trainer treats them. Reordering costs no turn, so reordering is a state of
its own with reward 0 rather than an action inside the move.

The behaviour policy is mixed, and that is the point
----------------------------------------------------
Half the episodes follow an existing trained policy with some exploration, and
half are random. Learning offline from one policy's data teaches you about states
that policy visits; the random half is what puts anything else in the file. A
dataset drawn only from a good policy has no examples of what the bad options
lead to, which is exactly what a max over actions needs to know.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from experiments.env.rewards import get as get_reward
from experiments.sarsa.features import FeatureSet, reorder_options
from pokelike.assets import AssetServer
from pokelike.core.game import Game

HERE = Path(__file__).parent
DATA = HERE / "output" / "data"
ROOT = HERE.parents[1]


def flat(sparse: dict[int, float]) -> list[float]:
    """A sparse feature dict as [i, v, i, v, …]: a third the JSON of a dict."""
    out: list[float] = []
    for i, v in sparse.items():
        out.append(i)
        out.append(round(v, 5))
    return out


def load_policy(weights: Path | None, fs: FeatureSet) -> list[float] | None:
    """Weights to steer the behaviour policy with, or None to play at random."""
    if weights is None:
        return None
    d = json.loads(Path(weights).read_text(encoding="utf-8"))
    w = d["weights"]
    if isinstance(w, dict):
        names = fs.names if hasattr(fs, "names") else None
        vec = [0.0] * fs.n
        from experiments.sarsa.features import feature_names
        index = {n: i for i, n in enumerate(feature_names(fs.groups))}
        for name, value in w.items():
            if name in index:
                vec[index[name]] = float(value)
        return vec
    return [float(v) for v in w]


def collect(episodes: int, seed0: int, port: int, out: Path,
            weights: Path | None = None, epsilon: float = 0.25,
            random_share: float = 0.5, reward: str = "progress",
            max_steps: int = 300, quiet: bool = False) -> Path:
    from tqdm import tqdm

    fs = FeatureSet()
    reward_fn = get_reward(reward)
    policy = load_policy(weights, fs)
    rng = random.Random(seed0)

    def q(x: dict[int, float]) -> float:
        return sum(policy[i] * v for i, v in x.items()) if policy else 0.0

    out.parent.mkdir(parents=True, exist_ok=True)
    server = AssetServer(ROOT / "site", port=port)
    server.start()
    game = Game(url=server.url)
    game.open()
    written = 0
    try:
        with out.open("w", encoding="utf-8") as fh:
            bar = tqdm(range(episodes), desc=out.stem, unit="ep", disable=quiet)
            for ep in bar:
                seed = seed0 + ep
                rng.seed(seed)
                greedy_episode = policy is not None and rng.random() >= random_share
                obs = game.reset(seed=seed)
                rows: list[list] = []

                def options(o, ph):
                    return reorder_options(o) if ph == "reorder" else (o.get("actions") or [])

                def settle(o, ph):
                    acts = options(o, ph)
                    if not acts and ph == "reorder":
                        ph = "action"
                        acts = options(o, ph)
                    return ph, acts

                def pick(o, acts) -> int:
                    if not greedy_episode or rng.random() < epsilon:
                        return rng.randrange(len(acts))
                    vals = [q(fs.of(o, a)) for a in acts]
                    best = max(vals)
                    return rng.choice([i for i, v in enumerate(vals) if v == best])

                phase, acts = settle(obs, "reorder")
                i = pick(obs, acts)
                x = fs.of(obs, acts[i])

                while True:
                    before = obs
                    if phase == "reorder":
                        b = acts[i]["b"]
                        if b is not None:
                            obs = game.reorder(0, b)
                        r, done = 0.0, False
                        phase = "action"
                    else:
                        obs = game.step(i)
                        done = (bool(obs.get("done")) or game.steps >= max_steps
                                or not obs.get("actions"))
                        after = obs if obs.get("run") else (game.last_alive or before)
                        r = reward_fn(before, after, done,
                                      obs.get("screen") == "win-screen")
                        phase = "reorder"

                    if done:
                        rows.append([flat(x), round(r, 4), []])
                        break

                    phase, acts = settle(obs, phase)
                    nexts = [flat(fs.of(obs, a)) for a in acts]
                    rows.append([flat(x), round(r, 4), nexts])
                    i = pick(obs, acts)
                    x = fs.of(obs, acts[i])

                alive = game.last_alive or {}
                fh.write(json.dumps({
                    "seed": seed,
                    "greedy": greedy_episode,
                    "badges": (alive.get("run") or {}).get("badges", 0),
                    "steps": game.steps,
                    "t": rows,
                }, separators=(",", ":")) + "\n")
                fh.flush()
                written += len(rows)
                bar.set_postfix(rows=written)
    finally:
        game.close()
        server.stop()
    return out


def fan_out(episodes: int, workers: int, seed0: int, port0: int,
            weights: Path | None, tag: str, **kw) -> list[Path]:
    """One process per worker, each its own browser, port and slice of seeds.

    The approach uses processes rather than threads because two Playwright sync
    instances cannot live in the same thread, and one game per thread is the rule
    the whole codebase is built on.
    """
    DATA.mkdir(parents=True, exist_ok=True)
    # The `logs/` directory is created here rather than assumed to exist, because
    # git does not track an empty directory, and a worker's log is opened before
    # the worker starts. A fresh clone would otherwise die before launching
    # anything.
    (HERE / "logs").mkdir(parents=True, exist_ok=True)
    per = episodes // workers
    procs, shards = [], []
    for k in range(workers):
        shard = DATA / f"{tag}-{k:02d}.jsonl"
        shards.append(shard)
        cmd = [sys.executable, "-m", "experiments.drrn.collect",
               "--episodes", str(per), "--seed0", str(seed0 + k * per * 10),
               "--port", str(port0 + k), "--out", str(shard), "--worker"]
        if weights:
            cmd += ["--weights", str(weights)]
        for flag, value in kw.items():
            cmd += [f"--{flag.replace('_', '-')}", str(value)]
        log = (HERE / "logs" / f"{tag}-{k:02d}.log").open("w")
        procs.append(subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
        print(f"  worker {k}: {per} episodes, port {port0 + k} -> {shard.name}")

    print(f"\n{workers} workers, {per * workers} episodes. Waiting.")
    started = time.monotonic()
    for k, p in enumerate(procs):
        p.wait()
        print(f"  worker {k} done ({p.returncode}) after "
              f"{(time.monotonic() - started) / 60:.1f} min")
    return shards


def main() -> int:
    p = argparse.ArgumentParser(description="Collect transitions for offline training.")
    p.add_argument("--episodes", type=int, default=400)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed0", type=int, default=100_000)
    p.add_argument("--port", type=int, default=8900)
    p.add_argument("--out", default=None)
    p.add_argument("--tag", default="mixed")
    p.add_argument("--weights", default=None,
                   help="policy to steer half the episodes with; random without it")
    p.add_argument("--epsilon", type=float, default=0.25)
    p.add_argument("--random-share", type=float, default=0.5)
    p.add_argument("--reward", default="progress")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()

    weights = Path(a.weights) if a.weights else None
    if a.workers > 1:
        shards = fan_out(a.episodes, a.workers, a.seed0, a.port, weights, a.tag,
                         epsilon=a.epsilon, random_share=a.random_share,
                         reward=a.reward)
        total = sum(1 for s in shards if s.is_file() for _ in s.open())
        print(f"\n{total} episodes across {len(shards)} shards in {DATA}")
        return 0

    out = Path(a.out) if a.out else DATA / f"{a.tag}.jsonl"
    collect(a.episodes, a.seed0, a.port, out, weights, a.epsilon,
            a.random_share, a.reward, quiet=a.worker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
