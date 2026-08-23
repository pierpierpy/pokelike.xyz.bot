"""Which prompt actually plays better?

    uv run python -m experiments.llm.compare --seeds 5 --bots llm-survivor,llm-explorer

Prompt engineering invites confident storytelling, so this module measures
outcomes on fixed seeds. Every prompt plays the same seeds, and the comparison
is paired. On each identical run, the question is whether survivor did better
than explorer.

The module compares the actual bots in `bots/`, loaded from disk, so what is
measured here is what a submission would be. A prompt cannot win the comparison
and then be quietly different by the time it is benchmarked. All LLM bots share
the one harness in `pokelike.bot.llm`, which is what makes the difference between
them a difference between prompts.

The metric is badges, because that is the game's own progression counter in Story
mode. The engine's score formula was written for the Battle Tower and two of its
terms never fire here, so ranking prompts by score would reward fighting rather
than getting further. See experiments/common/rewards.py.

Be aware of what this tool can and cannot tell you. The model is stochastic and a
run is high variance, so a handful of seeds will not separate two decent prompts.
Treat small differences as noise and look at the per-seed table rather than the
mean alone.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from pokelike.assets import AssetServer
from pokelike.bot import create
from pokelike.bot.catalogue import available as bots_on_disk
from pokelike.bot.llm import LLMBot
from pokelike.core.game import Game

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path(__file__).parent / "runs"


def play_one(game: Game, bot: LLMBot, seed: int, max_steps: int = 400) -> dict:
    obs = game.reset(seed=seed)
    bot.reset(seed)
    while not obs.get("done") and obs.get("actions") and game.steps < max_steps:
        obs = game.step(bot.act(obs))
    s = game.score() or {}
    alive = game.last_alive or {}
    return {
        "seed": seed,
        "badges": (alive.get("run") or {}).get("badges", 0),
        "score": s.get("points_no_time"),
        "steps": game.steps,
        "faints": (s.get("breakdown") or {}).get("faints", 0),
        "ending": obs.get("screen"),
        "calls": bot.calls,
        "tokens": bot.tokens_used,
        "fallbacks": bot.fallbacks,
    }


def compare(strategies: list[str], seeds: list[int], port: int = 8610) -> dict:
    from tqdm import tqdm

    # All bots are built up front because an LLM bot refuses to construct
    # without credentials, and discovering that after twenty minutes of the
    # first prompt playing is a waste of a comparison.
    made = {}
    for s in strategies:
        try:
            bot = create(s)
        except KeyError as e:
            raise SystemExit(str(e.args[0])) from e
        if not isinstance(bot, LLMBot):
            raise SystemExit(f"'{s}' is not an LLM bot, so there is no prompt to compare")
        made[s] = bot

    results: dict[str, list[dict]] = {s: [] for s in strategies}
    server = AssetServer(ROOT / "site", port=port)
    server.start()
    game = Game(url=server.url)
    game.open()
    started = time.monotonic()
    try:
        total = len(strategies) * len(seeds)
        bar = tqdm(total=total, desc="prompt comparison", unit="run")
        for strategy, bot in made.items():
            for seed in seeds:
                row = play_one(game, bot, seed)
                results[strategy].append(row)
                bar.set_postfix(strategy=strategy, seed=seed,
                                badges=row["badges"], steps=row["steps"])
                bar.update(1)
        bar.close()
    finally:
        game.close()
        server.stop()

    elapsed = time.monotonic() - started
    report(results, seeds, elapsed)

    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / "prompt_comparison.json"
    out.write_text(json.dumps({
        "model": os.environ.get("MODEL_ID", ""),
        "harness": LLMBot.harness_version,
        "seeds": seeds,
        "elapsed_minutes": round(elapsed / 60, 1),
        "results": results,
    }, indent=1), encoding="utf-8")
    print(f"\nsaved to {out}")
    return results


def report(results: dict[str, list[dict]], seeds: list[int], elapsed: float) -> None:
    print("\n" + "=" * 74)
    print("PER SEED (badges)")
    head = f"{'seed':>8}" + "".join(f"{s[:11]:>13}" for s in results)
    print(head)
    print("-" * len(head))
    for i, seed in enumerate(seeds):
        row = f"{seed:>8}"
        for s in results:
            row += f"{results[s][i]['badges']:>13}"
        print(row)

    print("\n" + "=" * 74)
    head = (f"{'bot':<15}{'badges~':>9}{'badges+':>9}{'score~':>9}"
            f"{'steps~':>9}{'faints~':>9}{'tokens/run':>12}{'fallbacks':>11}")
    print(head)
    print("-" * len(head))
    for s, rows in results.items():
        m = statistics.mean
        print(
            f"{s:<15}{m([r['badges'] for r in rows]):>9.2f}"
            f"{max(r['badges'] for r in rows):>9}"
            f"{m([r['score'] or 0 for r in rows]):>9.1f}"
            f"{m([r['steps'] for r in rows]):>9.1f}"
            f"{m([r['faints'] for r in rows]):>9.1f}"
            f"{m([r['tokens'] for r in rows]):>12.0f}"
            f"{sum(r['fallbacks'] for r in rows):>11}"
        )
    print(f"\n{elapsed / 60:.1f} minutes for {sum(len(r) for r in results.values())} runs")

    if len(results) == 2:
        a, b = list(results)
        diff = [x["badges"] - y["badges"] for x, y in zip(results[a], results[b])]
        wins = sum(1 for d in diff if d > 0)
        print(f"\npaired: {a} beats {b} on {wins}/{len(diff)} seeds, "
              f"mean difference {statistics.mean(diff):+.2f} badges")


def main() -> int:
    p = argparse.ArgumentParser(description="Compare LLM prompt bots on the same seeds.")
    p.add_argument("--bots", "--strategies", dest="bots",
                   default=",".join(n for n in bots_on_disk() if n.startswith("llm-")),
                   help="comma separated bot names (default: every llm-* bot in bots/)")
    p.add_argument("--seeds", type=int, default=5, help="how many seeds each bot plays")
    p.add_argument("--seed0", type=int, default=20_000)
    p.add_argument("--port", type=int, default=8610)
    a = p.parse_args()

    compare(
        strategies=[s.strip() for s in a.bots.split(",") if s.strip()],
        seeds=list(range(a.seed0, a.seed0 + a.seeds)),
        port=a.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
