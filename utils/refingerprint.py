#!/usr/bin/env python3
"""Re-stamp fingerprints in recorded results after a shared-file change.

WHEN TO RUN THIS: after changing core/game.py, core/browser.py or core/runner.py
in a way that does NOT affect what a recorded run measured (the run played under
the old code and got the score it got), but DOES change the hash the standings
would recompute today. The typical case is adding a feature (like regions) to the
shared driver that no harness version uses yet: the old results are correct, but
every one that fingerprinted the shared files will show as stale because the files
now hash differently.

WHEN NOT TO RUN THIS: if the change actually affects what a run would do. If a
future run under the same seed would get a different score, that is real drift and
the old row should stay stale until someone replays it. The tool cannot tell the
difference; that is a human judgment, and the `--reason` text is the record of it.

WHAT THIS DOES NOT DO: it does not make an old row comparable with a new one. The
row measured what it measured under the code of its day; re-stamping only stops the
standings shouting "stale" at rows for a change that cannot affect them, and the
`refingerprinted` entry is what keeps that honest.

It handles two kinds of result:
- bots/*/result.json: a single `fingerprint` hex string over bot.py + artifacts/
- llm-bench/*/results/*.json: a per-pass dict with 4-7 keys (frozen + shared)

Usage:
    python utils/refingerprint.py [--reason TEXT] [--write] [--force]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _tree_dirty() -> bool:
    """True if the working tree has uncommitted changes."""
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return bool(r.stdout.strip())


# ---------------------------------------------------------------------- bots


def _bot_fingerprint(bot_dir: Path) -> str:
    """Recompute a bot folder's fingerprint (same as arena/leaderboard/artifact.py)."""
    import hashlib
    h = hashlib.sha256()
    files = [bot_dir / "bot.py", *sorted((bot_dir / "artifacts").glob("**/*"))]
    for f in files:
        if not f.is_file():
            continue
        h.update(str(f.relative_to(bot_dir)).encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()


def _scan_bots() -> list[dict]:
    """Find bot results and check whether they need re-stamping.

    Out: list of dicts with path, kind, current fingerprint, and drift info.
    """
    entries = []
    bots_dir = ROOT / "bots"
    if not bots_dir.is_dir():
        return entries
    for d in sorted(bots_dir.iterdir()):
        r = d / "result.json"
        if not r.is_file():
            continue
        doc = json.loads(r.read_text(encoding="utf-8"))
        recorded = doc.get("fingerprint")
        if not recorded:
            continue
        current = _bot_fingerprint(d)
        entries.append({
            "path": r,
            "kind": "bot",
            "name": d.name,
            "recorded": recorded,
            "current": current,
            "match": recorded == current,
        })
    return entries


# ------------------------------------------------------------------- llm-bench


def _sha(path: Path) -> str:
    """SHA-256 prefix (16 hex chars), matching versions.fingerprints()."""
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _current_shared() -> dict[str, str]:
    """Hashes of the three shared files as they are on disk now."""
    core = ROOT / "src" / "pokelike" / "core"
    return {
        "shared/browser.py": _sha(core / "browser.py"),
        "shared/game.py": _sha(core / "game.py"),
        "shared/runner.py": _sha(core / "runner.py"),
    }


def _current_frozen(version: str) -> dict[str, str]:
    """Hashes of the frozen harness files for a given version."""
    harness = ROOT / "llm-bench" / version / "harness"
    out = {}
    for name in ("bot.py", "render.py", "bridge.js", "init.js"):
        p = harness / name
        if p.is_file():
            out[name] = _sha(p)
    return out


def _scan_llmbench() -> list[dict]:
    """Find llm-bench passes and check which have drifted fingerprint keys.

    Out: list of dicts with path, kind, pass index, and drift details.
    """
    entries = []
    bench = ROOT / "llm-bench"
    if not bench.is_dir():
        return entries
    shared = _current_shared()
    for vdir in sorted(bench.iterdir()):
        rdir = vdir / "results"
        if not rdir.is_dir():
            continue
        try:
            frozen = _current_frozen(vdir.name)
        except Exception:
            continue
        current_fp = {**frozen, **shared}
        for f in sorted(rdir.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            for i, p in enumerate(doc.get("passes", [])):
                pfp = p.get("fingerprint") or {}
                # Only check keys the pass actually recorded.
                drifted = {
                    k: {"was": v, "now": current_fp[k]}
                    for k, v in pfp.items()
                    if k in current_fp and current_fp[k] != v
                }
                entries.append({
                    "path": f,
                    "kind": "llm-bench",
                    "version": vdir.name,
                    "model": doc.get("model", f.stem),
                    "pass_index": i,
                    "recorded": pfp,
                    "current": current_fp,
                    "drifted_keys": drifted,
                    "match": len(drifted) == 0,
                })
    return entries


# --------------------------------------------------------------------- apply


def _apply_bot(entry: dict, reason: str, now_iso: str) -> None:
    """Rewrite a bot result.json with the new fingerprint and a log entry."""
    path = entry["path"]
    doc = json.loads(path.read_text(encoding="utf-8"))
    log_entry = {
        "on": now_iso,
        "was": {"fingerprint": entry["recorded"]},
        "now": {"fingerprint": entry["current"]},
        "why": reason,
    }
    doc.setdefault("refingerprinted", []).append(log_entry)
    doc["fingerprint"] = entry["current"]
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _apply_llmbench(entry: dict, reason: str, now_iso: str) -> None:
    """Rewrite an llm-bench result file, updating one pass's fingerprint."""
    path = entry["path"]
    doc = json.loads(path.read_text(encoding="utf-8"))
    p = doc["passes"][entry["pass_index"]]
    old_fp = dict(p["fingerprint"])
    # Replace drifted keys with current values.
    for k in entry["drifted_keys"]:
        p["fingerprint"][k] = entry["current"][k]
    log_entry = {
        "on": now_iso,
        "was": {k: v["was"] for k, v in entry["drifted_keys"].items()},
        "now": {k: v["now"] for k, v in entry["drifted_keys"].items()},
        "why": reason,
    }
    p.setdefault("refingerprinted", []).append(log_entry)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Re-stamp fingerprints in recorded results after a shared-file change.",
        epilog=(
            "Defaults to a dry run that prints what would change. "
            "Pass --write to actually modify the files on disk."
        ),
    )
    parser.add_argument(
        "--reason", required=True,
        help="Why this re-stamp is legitimate (stored in each affected file).",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Apply changes. Without this flag, only prints what would happen.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Allow running with a dirty working tree.",
    )
    args = parser.parse_args(argv)

    if not args.force and _tree_dirty():
        print("ERROR: working tree is dirty. Commit or stash first, or use --force.")
        sys.exit(1)

    bots = _scan_bots()
    passes = _scan_llmbench()
    all_entries = bots + passes

    matched = [e for e in all_entries if e["match"]]
    drifted = [e for e in all_entries if not e["match"]]

    # Print summary
    print(f"Scanned {len(all_entries)} recorded results "
          f"({len(bots)} bot, {len(passes)} llm-bench passes).")
    print(f"  {len(matched)} match (no action needed)")
    print(f"  {len(drifted)} drifted (would be re-stamped)")
    print()

    if not drifted:
        print("Nothing to do.")
        return

    for e in drifted:
        if e["kind"] == "bot":
            print(f"  DRIFT  bots/{e['name']}/result.json")
            print(f"         was: {e['recorded'][:16]}...")
            print(f"         now: {e['current'][:16]}...")
        else:
            keys = ", ".join(e["drifted_keys"])
            print(f"  DRIFT  llm-bench/{e['version']}/results/"
                  f"{e['path'].stem}.json pass {e['pass_index']}")
            print(f"         keys: {keys}")

    print()
    if not args.write:
        print("Dry run. Pass --write to apply.")
        return

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for e in drifted:
        if e["kind"] == "bot":
            _apply_bot(e, args.reason, now_iso)
        else:
            _apply_llmbench(e, args.reason, now_iso)

    print(f"Re-stamped {len(drifted)} result(s). Reason recorded in each file.")


if __name__ == "__main__":
    main()
