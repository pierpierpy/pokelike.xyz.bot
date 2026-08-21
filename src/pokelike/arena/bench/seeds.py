"""The fixed seed list and scoring helpers for the standard benchmark.

In: a list of run results. Out: summary statistics (mean, stdev, best, etc.).
"""

from __future__ import annotations

import hashlib
import statistics
from pathlib import Path
from typing import Any

# The official seed list. Fifty runs is enough to see past the luck without
# taking all afternoon, and it is held well away from the seeds used elsewhere
# in the project so nobody trains on the benchmark by accident.
STANDARD_SEEDS = list(range(10_000, 10_050))

CATEGORIES = ("rules", "rl", "llm", "human", "other")


def bundle_fingerprint(site: Path) -> dict[str, str]:
    """Identifies the exact version of the game that was played.

    In: the site directory. Out: a dict with the bundle filename and sha256.
    """
    bundle = next(Path(site).glob("js/bundle*.js"), None)
    if bundle is None:
        return {"file": "unknown", "sha256": "unknown"}
    return {
        "file": bundle.name,
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest()[:16],
    }


def summarise(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes summary statistics over a list of finished runs.

    In: the list of run dicts. Out: a summary dict with means, medians, bests.
    """
    scores = [r["score"] for r in runs if r.get("score") is not None]
    if not scores:
        return {"runs": len(runs)}
    return {
        "runs": len(runs),
        "score_mean": round(statistics.mean(scores), 1),
        "score_median": round(statistics.median(scores), 1),
        "score_best": max(scores),
        "score_worst": min(scores),
        "score_stdev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0.0,
        "badges_mean": round(statistics.mean([r.get("badges") or 0 for r in runs]), 2),
        "badges_best": max((r.get("badges") or 0) for r in runs),
        "maps_mean": round(statistics.mean([r.get("maps") or 0 for r in runs]), 2),
        "completed": sum(1 for r in runs if r.get("ending") == "win-screen"),
        "steps_mean": round(statistics.mean([r["steps"] for r in runs]), 1),
    }
