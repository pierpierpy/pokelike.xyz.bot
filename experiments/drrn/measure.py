"""Play the official 50 seeds and keep the per-seed rows.

    uv run python -m experiments.drrn.measure --bot experiments/drrn --tag drrn

This module uses the same protocol as `pokelike bot bench`, and the distinction
is the whole reason it is allowed to exist. `STANDARD_SEEDS` and `run_benchmark`
are imported from the package, so the seeds, the run loop, the step cap and the
score are the official ones to the letter. Nothing here chooses a seed.

What the module adds is that the rows survive. The command
`pokelike bot bench --bot experiments/drrn` prints the aggregate and records
nothing, which is right because a candidate measured by path is not a submission,
but that means the fifty per-seed results are computed and thrown away. Those rows
are what makes the comparison paired, and a paired test matters at this budget
because badges have a standard deviation near 0.7, so two means over 50 seeds
cannot resolve less than about 0.39 badges, while the same runs compared seed by
seed cut that to roughly 0.25-0.3. Seed difficulty is a large shared term, and
throwing the per-seed rows away costs exactly the effect size this experiment is
trying to detect.

The output goes into `output/runs/`, which is gitignored. The module can never
file a standings entry because only `pokelike bot bench` on a folder under
`bots/` does that.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from pokelike.assets import AssetServer
from pokelike.arena.bench import STANDARD_SEEDS, format_result, run_benchmark
from pokelike.bot import create
from pokelike.core.game import Game

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
RUNS = HERE / "output" / "runs"


def paired(mine: list[dict], theirs: list[dict], field: str = "badges") -> dict:
    """Seed-by-seed comparison against another recorded result on the same seeds.

    Refuses to align anything but identical seed lists. Comparing two different
    seed sets is the one mistake this file exists to avoid, and doing it silently
    would produce a number that looks like the others.
    """
    a = {r["seed"]: (r.get(field) or 0) for r in mine}
    b = {r["seed"]: (r.get(field) or 0) for r in theirs}
    if sorted(a) != sorted(b):
        raise SystemExit("the two results were not measured on the same seeds")
    seeds = sorted(a)
    d = [a[s] - b[s] for s in seeds]
    wins = sum(1 for x in d if x > 0)
    losses = sum(1 for x in d if x < 0)
    mean = statistics.mean(d)
    sd = statistics.stdev(d) if len(d) > 1 else 0.0
    sem = sd / len(d) ** 0.5 if sd else 0.0
    return {
        "n": len(d), "field": field,
        "mine": round(statistics.mean(a[s] for s in seeds), 3),
        "theirs": round(statistics.mean(b[s] for s in seeds), 3),
        "difference": round(mean, 3),
        "sd_of_difference": round(sd, 3),
        "t": round(mean / sem, 2) if sem else None,
        "wins": wins, "draws": len(d) - wins - losses, "losses": losses,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="The official 50 seeds, rows kept.")
    p.add_argument("--bot", default="experiments/drrn", help="bot name or path")
    p.add_argument("--tag", default="drrn", help="name for the file in output/runs/")
    p.add_argument("--against", default="bots/sarsa-v2/result.json",
                   help="a recorded result to compare against, seed by seed")
    p.add_argument("--port", type=int, default=8930)
    a = p.parse_args()

    bot = create(a.bot, seed=0)
    server = AssetServer(ROOT / "site", port=a.port)
    server.start()
    game = Game(url=server.url)
    game.open()
    try:
        result = run_benchmark(game, bot, bot_name=a.tag, site=ROOT / "site",
                               seeds=STANDARD_SEEDS, category="rl",
                               description=f"measured from {a.bot}, not recorded")
    finally:
        game.close()
        server.stop()

    print(format_result(result))

    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"{a.tag}_bench.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    other = Path(a.against)
    if other.is_file():
        theirs = json.loads(other.read_text(encoding="utf-8"))
        print(f"\n  paired against {other} on the same 50 seeds")
        for field in ("badges", "score"):
            c = paired(result["runs"], theirs["runs"], field)
            print(f"    {field:<7} {c['mine']:>7} vs {c['theirs']:>7}   "
                  f"diff {c['difference']:>+7}  t = {c['t']}   "
                  f"{c['wins']}W-{c['draws']}D-{c['losses']}L")

    print(f"\n  rows: {out}")
    print("  NOT a leaderboard entry: only `pokelike bot bench` on a folder in bots/ records one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
