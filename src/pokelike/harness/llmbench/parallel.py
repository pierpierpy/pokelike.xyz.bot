"""Parallel execution: fan-out across subprocesses.

Workers can outnumber cores because almost all wall clock is HTTP latency to
the model provider. Processes rather than threads because Playwright's sync API
is bound to the creating thread. Seeds are split in interleaved fashion and
merged back into seed order; the result is identical to a sequential pass.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ...arena.bench import _tok, live_fields, progress_bar
from .command import parse_settings
from ...logging import Conversations, PassLog
from .results import _as_pass
from .versions import (ROOT, cross_run_memory, fingerprints,
                       harness_path, script_paths, slug)


def fan_out(version: str, model: str, seeds: list[int], workers: int,
            site: Path, port0: int = 8500, endpoint: str | None = None,
            token: str | None = None, folder: Path | None = None,
            attempt: int = 1,
            settings: dict[str, Any] | None = None,
            region: int | str = 1, campaign: bool = False) -> dict[str, Any]:
    """Plays the seeds using several subprocesses, then assembles the pass dict."""
    import os
    import queue
    import subprocess
    import sys
    import threading

    # Refused for harnesses with cross-run memory: splitting seeds would give each
    # worker its own independent notebook, making the pass unreproducible.
    if cross_run_memory(version):
        raise RuntimeError(
            f"harness {version} carries the model's notes from one run into the "
            f"next, so its runs are not independent and the pass cannot be split "
            f"across {workers} workers.\n"
            f"  Run it sequentially: drop --workers (or pass --workers 1).\n"
            f"  A pass is one lifetime of {len(seeds)} runs, in seed order, which is "
            f"part of what {version} measures."
        )

    # Credentials passed via env, not argv, because argv is visible in ps.
    # Fingerprint taken before any worker starts.
    stamp = fingerprints(version)

    env = dict(os.environ)
    if endpoint:
        env["FW_ENDPOINT"] = endpoint
    if token:
        env["FW_TOKEN"] = token

    chunks = [seeds[k::workers] for k in range(workers)]
    chunks = [c for c in chunks if c]
    procs = []
    for k, chunk in enumerate(chunks):
        procs.append(subprocess.Popen(
            # Uses worker.py (not this module) to avoid double-import as __main__.
            [sys.executable, "-m", "pokelike.harness.llmbench.worker", "--worker",
             "--harness", version, "--model", model, "--port", str(port0 + k),
             *[a for k, v in (settings or {}).items()
               for a in ("--set", f"{k}={v}")],
             *(["--region", str(region)] if region != 1 else []),
             "--seeds", ",".join(str(s) for s in chunk)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        ))

    # Rows arrive as they finish from any worker; the bar tracks the whole pass.
    rows: list[dict[str, Any]] = []
    # Current state of each worker, overwritten on each heartbeat.
    live: dict[int, dict[str, Any]] = {}
    q: queue.Queue = queue.Queue()

    def pump(p: Any, k: int) -> None:
        for line in p.stdout:
            line = line.strip()
            if line.startswith("{"):
                q.put((k, json.loads(line)))
        q.put((k, None))

    for k, p in enumerate(procs):
        threading.Thread(target=pump, args=(p, k), daemon=True).start()

    log = PassLog(version, model, seeds, workers=len(procs), folder=folder,
                  attempt=attempt)
    bar = progress_bar(total=len(seeds), desc=f"{model} @ {version}",
                       unit="run", leave=True)

    def postfix() -> None:
        done = [r for r in rows if r.get("badges") is not None]
        # Token totals: finished runs plus in-flight estimates.
        t_in = (sum(r.get("tokens_in", 0) for r in rows)
                + sum(v.get("tokens_in", 0) for v in live.values()))
        t_out = (sum(r.get("tokens_out", 0) for r in rows)
                 + sum(v.get("tokens_out", 0) for v in live.values()))
        bar.set_postfix({
            "badges": round(sum(r["badges"] for r in done) / len(done), 2) if done else None,
            "in": _tok(t_in),
            "out": _tok(t_out),
            "fell": sum(r.get("fallbacks", 0) for r in rows),
            # Current worker positions (seed and depth) for a stuck-bar diagnostic.
            "now": " ".join(f"{v['seed']}@{v.get('layer', '?')}"
                            for v in sorted(live.values(), key=lambda x: x["seed"])),
        })

    ended = 0
    while ended < len(procs):
        k, item = q.get()
        if item is None:
            ended += 1
            live.pop(k, None)
            postfix()
            continue
        if item.get("live"):
            live[k] = item
            postfix()
            continue
        if "trace" in item:
            # Written by the parent so a parallel pass produces one trace file.
            log.decision(item["trace"])
            continue
        rows.append(item)
        log.run(item)
        live.pop(k, None)
        bar.update(1)
        postfix()
    bar.close()

    # A partial pass is discarded: a mean over whichever seeds survived is not
    # comparable to a full one.
    for k, p in enumerate(procs):
        p.wait()
        if p.returncode != 0:
            err = (p.stderr.read() or "").strip()[-600:]
            log.fail(f"worker {k} exited {p.returncode}: {err[-200:]}")
            log.close()
            raise RuntimeError(
                f"worker {k} exited {p.returncode}; discarding the whole pass "
                f"rather than recording a partial one.\n{err}"
            )
    if len(rows) != len(seeds):
        log.fail(f"collected {len(rows)} of {len(seeds)} runs")
        log.close()
        raise RuntimeError(
            f"expected {len(seeds)} runs, collected {len(rows)}; discarding the pass"
        )

    from ...arena.bench import bundle_fingerprint
    one = _as_pass(version, model, seeds, rows, bundle_fingerprint(site), {},
                   fingerprint=stamp)
    # Stamp recorded explicitly; the log paths are absolute and may not resolve on
    # the host reading the result (e.g. /app/... inside a container).
    one["stamp"] = log.stamp
    one["log"] = str(log.path)
    one["trace"] = str(log.trace_path)
    log.done(one)
    log.close()
    return one


def _worker() -> int:
    """One subprocess: runs its slice of seeds and prints one JSON row per finish."""
    import argparse

    from ...assets.server import AssetServer
    from ...bot.catalogue import load_class
    from ...core.game import Game
    from ...arena.bench import live_fields
    from ...core.runner import play_run
    from .versions import harness_path, script_paths, ROOT
    from .command import parse_settings

    p = argparse.ArgumentParser()
    p.add_argument("--worker", action="store_true")
    p.add_argument("--harness", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--seeds", required=True)
    # Passed through by fan_out so the worker uses the same harness settings.
    p.add_argument("--set", action="append", dest="settings", default=[])
    a = p.parse_args()

    seeds = [int(s) for s in a.seeds.split(",") if s]
    cls = load_class(harness_path(a.harness))
    bot = cls(seed=0, model=a.model, **parse_settings(a.settings))
    server = AssetServer(ROOT / "site", port=a.port)
    server.start()
    game = Game(url=server.url, **script_paths(a.harness))
    game.open()
    try:
        for seed in seeds:
            began = time.time()

            # Heartbeat every 5 steps so the parent's progress bar shows movement.
            # The observation is kept every step for the decision trace's map.
            last: dict[str, Any] = {}

            def live(obs, steps, _seed=seed):
                last["obs"] = obs
                if steps % 5:
                    return
                # Raw counts; the parent formats them after summing across workers.
                print(json.dumps({
                    "live": True, "seed": _seed, "step": steps,
                    "tokens_in": bot.tokens_in, "tokens_out": bot.tokens_out,
                    **live_fields(obs),
                }), flush=True)

            drawn = [""]

            def decided(entry, _seed=seed):
                # Same enrichments as the sequential path for dashboard consistency.
                extra: dict[str, Any] = {}
                called = bot.tool_calls_made()
                if called:
                    extra["tools"] = called
                if ((last.get("obs") or {}).get("map") or {}).get("nodes"):
                    from ...core import render

                    picture = render.map_view(last["obs"]["map"])
                    if picture and picture != drawn[0]:
                        extra["map_view"] = picture
                        drawn[0] = picture
                print(json.dumps({"trace": {
                    "seed": _seed,
                    "run_in": bot.tokens_in, "run_out": bot.tokens_out,
                    **entry, **extra,
                }}, ensure_ascii=False), flush=True)

            full = play_run(game, bot, seed, max_steps=400, on_step=live,
                            on_decision=decided)
            n = bot.metadata()
            row = {k: full[k] for k in ("seed", "steps", "score", "badges", "maps",
                                        "kos", "faints", "ending", "stalled")}
            row.update(tokens_in=n.get("tokens_in", 0), tokens_out=n.get("tokens_out", 0),
                       calls=n.get("calls", 0), turns=n.get("turns", 0),
                       fallbacks=n.get("fallbacks", 0), retries=n.get("retries", 0),
                       secs=round(time.time() - began, 1))
            print(json.dumps(row), flush=True)
    finally:
        game.close()
        server.stop()
    return 0

