"""Recording, loading, and summarising benchmark results.

Each model has one JSON file per harness version; every pass is appended to it.
Statistics are always derived at read time, never stored.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...arena.bench import STANDARD_SEEDS, summarise
from ...logging import LEARN_K
from .versions import (BROWSER, GAME, RUNNER, _bench, cross_run_memory,
                       fingerprints, slug, versions)


# ------------------------------------------------------------------- recording


def result_path(version: str, model: str) -> Path:
    """Path where this model's results are stored under this harness version."""
    return _bench() / version / "results" / f"{slug(model)}.json"


def record(version: str, model: str, one_pass: dict[str, Any]) -> Path:
    """Appends a pass to this model's result file.

    Multiple passes of the same model are needed to distinguish real gaps from
    sampling noise.
    """
    path = result_path(version, model)
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"model": model, "harness": version, "passes": []}
    # Fingerprint stored per pass, not per file: different passes may have run
    # against different code.
    doc["passes"].append(one_pass)
    doc["model"] = model
    doc["harness"] = version
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def load(version: str) -> list[dict[str, Any]]:
    """Loads all result files for a harness version."""
    d = _bench() / version / "results"
    if not d.is_dir():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))]


# ------------------------------------------------------------------ statistics


def learning(passes: list[dict[str, Any]], k: int = LEARN_K) -> dict[str, Any]:
    """First k runs of a pass vs. its last k, averaged over passes.

    Computed in play order (via the `order` field), not seed order, because the
    model's notes accumulate over the pass. Per pass then averaged, so different
    lifetimes are never mixed.
    """
    firsts: list[float] = []
    lasts: list[float] = []
    for p in passes:
        runs = p.get("runs") or []
        # Need at least 2k runs to avoid overlap between the two halves.
        if len(runs) < 2 * k:
            continue
        played = sorted(runs, key=lambda r: (r.get("order") is None, r.get("order"),
                                             r.get("seed")))
        firsts.append(statistics.mean([r.get("badges") or 0 for r in played[:k]]))
        lasts.append(statistics.mean([r.get("badges") or 0 for r in played[-k:]]))
    if not firsts:
        return {"k": k, "first": None, "last": None, "delta": None, "passes": 0}
    first, last = statistics.mean(firsts), statistics.mean(lasts)
    return {
        "k": k,
        "first": round(first, 2),
        "last": round(last, 2),
        "delta": round(last - first, 2),
        "passes": len(firsts),
    }


def stats(doc: dict[str, Any], version: str | None = None) -> dict[str, Any]:
    """Pooled statistics over every run of every pass, with across-pass spread.

    Statistics are derived here at read time, never stored in the result file.
    """
    passes = doc.get("passes") or []
    runs = [r for p in passes for r in (p.get("runs") or [])]
    if not runs:
        return {"model": doc.get("model"), "passes": 0, "runs": 0}

    badges = [r.get("badges") or 0 for r in runs]
    sd = statistics.stdev(badges) if len(badges) > 1 else 0.0
    per_pass = [
        statistics.mean([r.get("badges") or 0 for r in p["runs"]])
        for p in passes if p.get("runs")
    ]
    tok_in = sum(r.get("tokens_in") or 0 for r in runs)
    tok_out = sum(r.get("tokens_out") or 0 for r in runs)
    turns = sum(r.get("turns") or 0 for r in runs)
    falls = sum(r.get("fallbacks") or 0 for r in runs)

    out = {
        "model": doc.get("model"),
        "passes": len(passes),
        "runs": len(runs),
        # Region: at the doc level, or inferred from the first pass that carries one.
        "region": (doc.get("region")
                   or next((p.get("region") for p in passes if p.get("region")), None)),
        "badges_mean": round(statistics.mean(badges), 3),
        # The number that decides whether any gap in this table is real.
        "badges_sem": round(sd / len(badges) ** 0.5, 3) if sd else 0.0,
        "badges_median": statistics.median(badges),
        "badges_best": max(badges),
        # Runs that reached the win screen. Badges cap at 8, so without this
        # column the standings cannot distinguish a win from an Elite Four loss.
        "won": sum(1 for r in runs if r.get("ending") == "win-screen"),
        # Spread across passes: isolates the model's sampling noise from seed luck.
        "pass_spread": round(max(per_pass) - min(per_pass), 3) if len(per_pass) > 1 else None,
        "tokens_in_per_run": round(tok_in / len(runs)),
        "tokens_out_per_run": round(tok_out / len(runs)),
        "tokens_total": tok_in + tok_out,
        "fallback_rate": round(falls / turns, 3) if turns else 0.0,
        "notes_kept": (
            max((r.get("notes_kept") or 0) for r in runs)
            if any("notes_kept" in r for r in runs) else None
        ),
        "learning": learning(passes),
    }
    if version:
        # Looked up through the package so that tests can monkeypatch
        # `L.fingerprints` and have this function see the replacement.
        import sys
        _pkg = sys.modules[__package__]
        now = _pkg.fingerprints(version)
        used = {k: v for p in passes for k, v in (p.get("fingerprint") or {}).items()}
        # Compared key by key over the keys the pass recorded. A key the pass never
        # had is not evidence of drift; it just means the fingerprint grew later.
        out["stale"] = any(now[k] != v for k, v in used.items() if k in now)
    return out


# --------------------------------------------------------------- pass assembly


def _as_pass(version: str, model: str, seeds: list[int], runs: list[dict[str, Any]],
             game: dict[str, str], notes: dict[str, Any],
             fingerprint: dict[str, str] | None = None,
             region: str | None = None) -> dict[str, Any]:
    """Assembles a pass dict ready for recording.

    The fingerprint should be taken by the caller before play starts. If none is
    supplied, this function computes it from the current disk state.
    """
    turns = sum(r.get("turns") or 0 for r in runs)
    falls = sum(r.get("fallbacks") or 0 for r in runs)
    out = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "harness": version,
        "fingerprint": fingerprint or fingerprints(version),
        "game": game,
        "seeds": seeds,
        "summary": summarise(runs),
        "tokens_in": sum(r.get("tokens_in") or 0 for r in runs),
        "tokens_out": sum(r.get("tokens_out") or 0 for r in runs),
        "retries": sum(r.get("retries") or 0 for r in runs),
        "fallback_rate": round(falls / turns, 3) if turns else 0.0,
        "notes": notes,
        "runs": sorted(runs, key=lambda r: r["seed"]),
    }
    # Region: only recorded when it is not kanto, so existing files stay valid.
    if region and region != "kanto":
        out["region"] = region
    return out
