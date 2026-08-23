"""Recording, loading, and summarising benchmark results.

Each model has one JSON file per harness version, and every pass is appended to
that file. Statistics are always derived at read time and never stored.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...arena.bench import STANDARD_SEEDS, summarise
from ...shared.fingerprint import BEHAVIOUR_SCHEMA
from ...logging import LEARN_K
from .versions import (BROWSER, GAME, RUNNER, _bench, cross_run_memory,
                       fingerprints, slug, versions)


# ------------------------------------------------------------------- recording


def _settings_key(settings: dict[str, Any] | None) -> tuple:
    """Returns a hashable, order-independent key for a pass's --set overrides."""
    return tuple(sorted((settings or {}).items()))


def stats_by_settings(doc: dict[str, Any],
                      version: str | None = None) -> list[dict[str, Any]]:
    """Returns one `stats()` row per distinct `--set` group in this model's passes.

    A plain pass (no `--set`) and a pass with `--set reasoning=low` are two
    different questions asked of the same model. Pooling them into one row
    would average over that difference rather than showing it. Passes that
    share the same settings (e.g. two `reasoning=low` passes, run to check
    sampling noise) are still pooled together, exactly as `stats()` already
    does for passes with no settings at all.
    """
    passes = doc.get("passes") or []
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for p in passes:
        groups.setdefault(_settings_key(p.get("settings")), []).append(p)
    return [stats(doc, version, passes=group) for group in groups.values()]


def result_path(version: str, model: str) -> Path:
    """Returns the path where this model's results are stored under this harness version."""
    return _bench() / version / "results" / f"{slug(model)}.json"


def record(version: str, model: str, one_pass: dict[str, Any]) -> Path:
    """Appends a pass to this model's result file.

    Multiple passes of the same model are needed to distinguish real score gaps
    from sampling noise.
    """
    path = result_path(version, model)
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"model": model, "harness": version, "passes": []}
    # The fingerprint is stored per pass rather than per file, because different
    # passes may have run against different code.
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
    """Compares the first k runs of a pass to its last k, averaged over passes.

    The comparison uses play order (via the `order` field) rather than seed order,
    because the model's notes accumulate over the pass. Each pass is evaluated
    independently and the results are averaged, so different lifetimes are never
    mixed.
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


def _elite4_cleared(run: dict[str, Any]) -> int:
    """Returns how many Elite Fours this one run beat.

    The `regions_cleared` field is the real count for a run that played several
    regions in one campaign. For a run that played only one region, the value is 1
    if that region's Elite Four was beaten and 0 otherwise. Every run recorded
    before this field existed has no `regions_cleared` key at all. For those older
    runs a single region was always what got played, so the same rule (win-screen
    means the one Elite Four in that run was beaten) gives the same answer without
    a backfill script.
    """
    if "regions_cleared" in run:
        return run["regions_cleared"] or 0
    return 1 if run.get("ending") == "win-screen" else 0


def stats(doc: dict[str, Any], version: str | None = None,
          passes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Computes pooled statistics over every run of every pass, with across-pass spread.

    Statistics are derived here at read time and never stored in the result file.
    Two passes of the same model with different `--set` overrides answer a
    different question (a row for `reasoning=low` is not the same experiment as
    one for `reasoning=high`), so a caller comparing settings should call this
    once per settings group rather than once per model. The `passes` parameter may
    be given explicitly to restrict which of the file's passes are pooled. The
    default pools every pass in the file, unchanged from before this parameter
    existed.
    """
    passes = passes if passes is not None else (doc.get("passes") or [])
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
        # Region is taken from the doc level, or inferred from the first pass that carries one.
        "region": (doc.get("region")
                   or next((p.get("region") for p in passes if p.get("region")), None)),
        "badges_mean": round(statistics.mean(badges), 3),
        # The number that decides whether any gap in this table is real.
        "badges_sem": round(sd / len(badges) ** 0.5, 3) if sd else 0.0,
        "badges_median": statistics.median(badges),
        "badges_best": max(badges),
        # This counts runs that reached the win screen. Badges cap at 8, so without
        # this column the standings cannot distinguish a win from an Elite Four loss.
        "won": sum(1 for r in runs if r.get("ending") == "win-screen"),
        # How many Elite Fours this group's runs beat in total. For a
        # single-region pass this is the same count as `won` (one Elite Four
        # per run, at most). For a multi-region campaign pass it can exceed
        # `won`, since a run that dies in region 3 still cleared regions 1-2.
        "elite4": sum(_elite4_cleared(r) for r in runs),
        # Spread across passes, which isolates the model's sampling noise from seed luck.
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
        # The --set overrides shared by every pass in this group, or None for a
        # plain pass. Distinguishes rows like `reasoning=low` from `reasoning=high`
        # in a table that would otherwise show the same model name twice.
        "settings": next((p.get("settings") for p in passes if p.get("settings")), None),
    }
    if version:
        # Looked up through the package so that tests can monkeypatch
        # `L.fingerprints` and have this function see the replacement.
        import sys
        _pkg = sys.modules[__package__]
        now = _pkg.fingerprints(version)
        used = {k: v for p in passes for k, v in (p.get("fingerprint") or {}).items()}
        # Compared key by key over the keys the pass recorded. A key the pass
        # never had is not evidence of drift; the absence just means the
        # fingerprint grew after that pass was recorded.
        code_drifted = any(now[k] != v for k, v in used.items() if k in now)
        out["code_drifted"] = code_drifted
        # A changed file hash alone does not mean a score moved, because a comment
        # or a rename changes every hash without affecting any decision. The
        # `behaviour` hash is the true check, and only a pass that recorded one can
        # be cleared by it. A pass from before this field existed falls back to
        # the older, blunter code-drift check.
        behaviours = {p.get("behaviour") for p in passes if p.get("behaviour")}
        if code_drifted and behaviours:
            try:
                current_behaviour = _pkg.behaviour(version, _pkg.ROOT / "site")
            except Exception:
                current_behaviour = None
            out["stale"] = current_behaviour is None or any(
                b != current_behaviour for b in behaviours
            )
        else:
            out["stale"] = code_drifted
    return out


# --------------------------------------------------------------- pass assembly


def _as_pass(version: str, model: str, seeds: list[int], runs: list[dict[str, Any]],
             game: dict[str, str], notes: dict[str, Any],
             fingerprint: dict[str, str] | None = None,
             region: str | None = None,
             settings: dict[str, Any] | None = None,
             site: Any = None) -> dict[str, Any]:
    """Assembles a pass dict ready for recording.

    The caller should take the fingerprint before play starts. If none is supplied,
    this function computes the fingerprint from the current disk state. The
    `settings` parameter is whatever `--set` overrode for this pass (e.g.
    `{"reasoning": "low"}`). Two passes of the same model with different settings
    answer a different question, so both the result file and the standings keep
    them apart. The `site` parameter is the asset server root. When given, this
    function also records a `behaviour` hash (see `versions.behaviour`), which is a
    short deterministic replay through this version's own engine so that a later
    reader can distinguish "the files changed" from "a decision changed." The
    behaviour hash is omitted when `site` is not given, so a caller that cannot
    afford the replay (a unit test, a dry run) still gets a valid pass.
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
    # The region is only recorded when it is not kanto, so existing files stay valid.
    if region and region != "kanto":
        out["region"] = region
    # Settings are only recorded when --set overrode something, so a plain pass
    # (no --set at all) still looks exactly like one recorded before this field existed.
    if settings:
        out["settings"] = settings
    if site is not None:
        try:
            import sys
            _pkg = sys.modules[__package__]
            out["behaviour"] = _pkg.behaviour(version, site)
            out["behaviour_schema"] = BEHAVIOUR_SCHEMA
        except Exception:
            # A replay failure should never lose an otherwise-good pass. The row
            # simply carries no behaviour hash, exactly like one recorded before
            # this field existed.
            pass
    return out
