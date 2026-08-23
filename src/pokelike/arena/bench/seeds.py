"""The fixed seed list and scoring helpers for the standard benchmark."""

from __future__ import annotations

import hashlib
import statistics
from pathlib import Path
from typing import Any

# Fifty fixed seeds, far from those used elsewhere, so nobody trains on them.
STANDARD_SEEDS = list(range(10_000, 10_050))

CATEGORIES = ("rules", "rl", "llm", "human", "other")


def bundle_fingerprint(site: Path) -> dict[str, str]:
    """Returns the bundle filename and sha256 for the game version on disk."""
    bundle = next(Path(site).glob("js/bundle*.js"), None)
    if bundle is None:
        return {"file": "unknown", "sha256": "unknown"}
    return {
        "file": bundle.name,
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest()[:16],
    }


def summarise(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes summary statistics (means, medians, bests) over finished runs."""
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
