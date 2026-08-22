"""Recording, loading, and summarising benchmark results.

A result is one file per model with every pass appended, because it is the
comparable record: ten commands over three days build up one model's history, and
splitting it by invocation would destroy the only thing it is for.
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
    """Returns the path where a model's results are stored.

    In: harness version, model id. Out: Path to the JSON file.
    """
    return _bench() / version / "results" / f"{slug(model)}.json"


def record(version: str, model: str, one_pass: dict[str, Any]) -> Path:
    """Appends a pass to this model's file.

    In: the harness version, the model id, the pass dict. Out: the path written.
    """
    # Appends rather than replaces, because two passes of the same model are the
    # only way to know whether the gap to another model is bigger than the model's
    # own variance.
    path = result_path(version, model)
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"model": model, "harness": version, "passes": []}
    # Recorded per pass, not per file: a pass played before render.py changed and
    # one played after are different measurements, and the file must be able to
    # say so rather than carrying one hash for both.
    doc["passes"].append(one_pass)
    doc["model"] = model
    doc["harness"] = version
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def load(version: str) -> list[dict[str, Any]]:
    """Loads all result files for a harness version.

    In: harness version string. Out: list of result dicts (one per model).
    """
    d = _bench() / version / "results"
    if not d.is_dir():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))]


# ------------------------------------------------------------------ statistics


def learning(passes: list[dict[str, Any]], k: int = LEARN_K) -> dict[str, Any]:
    """First k runs of a pass against its last k, averaged over passes.

    In: list of pass dicts, number of runs at each end. Out: dict with k, first,
    last, delta, passes.
    """
    # The number a memory harness is for. Its mean is still comparable to a
    # memoryless version, but a mean over a learning curve averages a naive model
    # with a practised one and hides the only effect being tested.
    #
    # Computed in the order the runs were PLAYED, not seed order: the fortieth run
    # had thirty-nine runs' worth of notes behind it, and rows are stored sorted by
    # seed. Falls back to seed order for rows recorded before `order` existed, which
    # is the same thing whenever the seed list was ascending.
    #
    # Per pass, then averaged, rather than pooling every run: pooling would compare
    # the first k of one pass against the last k of another, which are different
    # lifetimes.
    firsts: list[float] = []
    lasts: list[float] = []
    for p in passes:
        runs = p.get("runs") or []
        # Fewer than 2k runs and the two halves would overlap, which would show a
        # gain that is really the same runs counted twice.
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

    In: a model's result dict, optional harness version. Out: summary dict with
    means, SEM, tokens, fallback rate, staleness.
    """
    # Statistics are derived here and never stored: the rows are the record, and a
    # stored average is a number that cannot be checked and goes wrong silently when
    # the definition changes.
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
        # Runs that finished the game. Badges STOP AT 8, because the engine has eight
        # gym leaders and the Elite Four that follows them awards none, so a model
        # that WINS scores exactly what one that reaches the Elite Four and dies
        # scores. Without this column the ranking cannot tell them apart.
        "won": sum(1 for r in runs if r.get("ending") == "win-screen"),
        # Sampling noise on its own: the seeds are fixed, so what moves between
        # passes is the model.
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
        # Compared KEY BY KEY, over the keys the passes actually recorded.
        #
        # Whole-dict equality tied the answer to how many files we happen to
        # fingerprint TODAY, not to whether anything moved: the day a file is
        # added to `fingerprints()`, every result ever recorded gained a key it
        # could not have, and every row would claim its code had changed while
        # nothing had been touched. A key the pass never recorded is not
        # evidence of drift, it is the absence of evidence.
        out["stale"] = any(now[k] != v for k, v in used.items() if k in now)
    return out


# --------------------------------------------------------------- pass assembly


def _as_pass(version: str, model: str, seeds: list[int], runs: list[dict[str, Any]],
             game: dict[str, str], notes: dict[str, Any],
             fingerprint: dict[str, str] | None = None,
             region: str | None = None) -> dict[str, Any]:
    """Assembles a pass dict ready for recording.

    In: version, model, seeds, run rows, game fingerprint, notes, optional
    harness fingerprint, optional region. Out: the complete pass dict.
    """
    # `fingerprint` is taken by the CALLER, before the first seed is played, and
    # passed in. Hashing the harness here instead would hash it half an hour later:
    # edit the file mid-pass and the row would claim the code it never ran, while
    # matching disk perfectly: a false statement that nothing could detect, which
    # is the exact opposite of what a fingerprint is for. Recomputed here only when
    # no caller supplied one, so the function stays usable on its own.
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
