"""Parallel execution: fan-out across subprocesses and the worker entry point.

Worth much more here than for a local bot. An LLM run is about twenty turns and
one HTTP request each, so almost all of its wall clock is spent waiting on the
provider rather than on this machine: which means workers can outnumber cores
and still help. Fifty seeds sequentially is half an hour; eight at a time is a
few minutes, for the same tokens and the same money.

Processes, not threads, and not by choice: Playwright's sync API is bound to the
thread that created it, so one game per process is the only arrangement that
works. `experiments/drrn/collect.py` fans out the same way for the same reason.

Seeds are independent, so splitting them changes nothing about the result: the
merged pass is what a sequential run would have produced, sorted back into seed
order. Interleaved rather than in blocks, so a worker that draws a run of long
games does not become the one everybody waits for.
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
    """Plays the same pass using several subprocesses at once.

    In: version, model, seeds, worker count, site path, base port, credentials,
    log folder, attempt number, settings. Out: the assembled pass dict.
    """
    import os
    import queue
    import subprocess
    import sys
    import threading

    # Not for a harness whose model keeps notes between runs. Splitting the seeds
    # would give each worker its own notebook and each note to a tenth of the pass,
    # so the result would depend on how the seeds happened to be dealt and on which
    # worker finished first. Refused rather than warned about: the pass would look
    # exactly like a valid one, and the recorded row would be unreproducible in a
    # way nothing in the file would reveal.
    if cross_run_memory(version):
        raise RuntimeError(
            f"harness {version} carries the model's notes from one run into the "
            f"next, so its runs are not independent and the pass cannot be split "
            f"across {workers} workers.\n"
            f"  Run it sequentially: drop --workers (or pass --workers 1).\n"
            f"  A pass is one lifetime of {len(seeds)} runs, in seed order, which is "
            f"part of what {version} measures."
        )

    # Credentials reach the workers through the environment even when they came
    # from a flag, and NOT on their command line: every process list on the
    # machine shows argv, so a key passed that way would be readable by any other
    # user for as long as the benchmark runs. The model id is not a secret and
    # stays visible, which is what makes `ps` useful here.
    # Before a single worker starts, for the same reason as the sequential path.
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
            # `worker.py` and not this module: this one is already imported by the
            # package, and running an imported module with `-m` imports it a second
            # time as `__main__`. worker.py exists to be that entry and nothing else.
            [sys.executable, "-m", "pokelike.harness.llmbench.worker", "--worker",
             "--harness", version, "--model", model, "--port", str(port0 + k),
             *[a for k, v in (settings or {}).items()
               for a in ("--set", f"{k}={v}")],
             *(["--region", str(region)] if region != 1 else []),
             "--seeds", ",".join(str(s) for s in chunk)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        ))

    # Rows arrive as they finish, from whichever worker finished them, so the bar
    # measures the whole pass rather than one process's share of it.
    rows: list[dict[str, Any]] = []
    # Where each worker is right now, keyed by worker. Overwritten rather than
    # appended: this is a reading, not a record: the record is the row that
    # arrives when the run finishes.
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
        # Finished runs plus what the in-flight ones have spent so far, in and out
        # kept apart: output is priced several times higher, so one total cannot be
        # turned into a bill.
        t_in = (sum(r.get("tokens_in", 0) for r in rows)
                + sum(v.get("tokens_in", 0) for v in live.values()))
        t_out = (sum(r.get("tokens_out", 0) for r in rows)
                 + sum(v.get("tokens_out", 0) for v in live.values()))
        bar.set_postfix({
            "badges": round(sum(r["badges"] for r in done) / len(done), 2) if done else None,
            "in": _tok(t_in),
            "out": _tok(t_out),
            "fell": sum(r.get("fallbacks", 0) for r in rows),
            # What the workers are on at this instant, so a bar stuck on the same
            # count still shows movement: or shows that there is none. Seed and
            # depth only: badges and steps mid-run are noise, and the row written
            # when the run finishes carries both. Passed as a dict rather than as
            # keywords because tqdm renders numbers through its own formatter, and
            # a seed becomes `1e+4`.
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
            # Written by the parent rather than by each worker, so a parallel pass
            # produces ONE trace file instead of one per process: and so no two
            # processes ever write the same file.
            log.decision(item["trace"])
            continue
        rows.append(item)
        log.run(item)
        live.pop(k, None)
        bar.update(1)
        postfix()
    bar.close()

    # All or nothing. A pass with 43 of 50 seeds in it is worse than no pass: the
    # mean would be over whichever seeds happened to survive, and nothing in the
    # file would say so.
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
    # Named explicitly, not only implied by the paths below: those are absolute
    # and were written inside the container, so `/app/...` is a directory that does
    # not exist on the host reading the result. The stamp is the portable half.
    one["stamp"] = log.stamp
    one["log"] = str(log.path)
    one["trace"] = str(log.trace_path)
    log.done(one)
    log.close()
    return one


def _worker() -> int:
    """One subprocess, one browser, its slice of the seeds. Prints JSON rows.

    In: command-line args (harness, model, port, seeds, settings). Out: exit code.
    """
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
    # Passed through by `fan_out`. Without it a parallel pass would run the
    # harness defaults while the pass said it ran what was asked for.
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

            # A worker's run takes one to three minutes and the parent cannot see
            # inside it, so without this the shared bar has nothing to say for
            # minutes at a time. Every fifth step, because the point is "it is
            # moving and here is where", not a transcript.
            #
            # The observation itself is kept EVERY step, which is not the same thing:
            # the decision written below draws the map from it, and a map four steps
            # stale is a map of somewhere else.
            last: dict[str, Any] = {}

            def live(obs, steps, _seed=seed):
                last["obs"] = obs
                if steps % 5:
                    return
                # Raw counts, not the bar's pretty strings: the parent has to add
                # them up across workers before anyone formats anything.
                print(json.dumps({
                    "live": True, "seed": _seed, "step": steps,
                    "tokens_in": bot.tokens_in, "tokens_out": bot.tokens_out,
                    **live_fields(obs),
                }), flush=True)

            drawn = [""]

            def decided(entry, _seed=seed):
                # The same additions the sequential path makes, and for the same
                # reasons. Kept in step deliberately: a trace read by the dashboard
                # cannot say less about a pass because four processes played it.
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

