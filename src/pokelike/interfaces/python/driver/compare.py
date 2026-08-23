"""Compare several bots over identical seeds, paired.

Seeds are paired so that the comparison controls for map variance rather than
measuring who drew nicer maps.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from ....core.runner import play_run
from tqdm import tqdm

from .session import SITE, session


def compare(bots: dict[str, Any], seeds, baseline: str | None = None,
            site: Path | str = SITE,
            region: int | str = 1) -> dict[str, Any]:
    """Run several bots over the same seeds and return a paired comparison.

    Returns {"runs": {name: [row, ...]}, "table": str}. If no baseline is
    given, a RandomBot is added to fill that role.
    """
    from ....bot.random_bot import RandomBot

    seeds = list(seeds)
    entrants = dict(bots)
    if baseline is None:
        baseline = "random"
        entrants.setdefault("random", RandomBot(seed=0))
    if baseline not in entrants:
        raise KeyError(f"baseline '{baseline}' is not one of: {', '.join(entrants)}")

    runs: dict[str, list[dict]] = {}
    with session(site=site) as game:
        for name, bot in tqdm(entrants.items()):
            runs[name] = [play_run(game, bot, s, region=region) for s in seeds]
    return {"runs": runs, "table": format_comparison(runs, baseline)}


def format_comparison(runs: dict[str, list[dict]], baseline: str) -> str:
    """Format the paired comparison table, ranked by badges.

    Reports wins/draws/losses and a t statistic rather than only a mean.
    """
    m = statistics.mean
    base = runs.get(baseline) or []
    head = (f"{'bot':<18}{'badges~':>9}{'badges+':>9}{'score~':>9}"
            f"{'steps~':>8}{'vs ' + baseline:>14}{'t':>8}")
    out = [head, "-" * len(head)]
    for name in sorted(runs, key=lambda k: -m(r["badges"] for r in runs[k])):
        rows = runs[name]
        cell = t_cell = ""
        if base and name != baseline:
            diff = [a["badges"] - b["badges"] for a, b in zip(rows, base)]
            w = sum(1 for d in diff if d > 0)
            losses = sum(1 for d in diff if d < 0)
            cell = f"{w}W-{len(diff) - w - losses}D-{losses}L"
            if len(diff) > 1 and statistics.stdev(diff) > 0:
                t_cell = f"{m(diff) / (statistics.stdev(diff) / len(diff) ** 0.5):.2f}"
        out.append(
            f"{name:<18}{m(r['badges'] for r in rows):>9.2f}"
            f"{max(r['badges'] for r in rows):>9}"
            f"{m(r['score'] or 0 for r in rows):>9.1f}"
            f"{m(r['steps'] for r in rows):>8.1f}{cell:>14}{t_cell:>8}"
        )
    out += ["-" * len(head), "paired on identical seeds; |t| over 2 is worth believing"]
    return "\n".join(out)
