"""Running a pass by playing one model over the seed list sequentially.

Sequential execution is required when the harness carries cross-run memory,
because runs depend on each other. For independent seeds with multiple
subprocesses, see parallel.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ...arena.bench import STANDARD_SEEDS, run_benchmark
from ...core.browser import normalise_region, region_name
from ...logging.trace import enrich_decision
from ...logging import CHAT_SUFFIX, Conversations, PassLog
from .results import _as_pass, learning
from .versions import (ROOT, cross_run_memory, fingerprints,
                       harness_path, script_paths, slug)

# Re-export parallel pieces so the package __init__ can import them from here
# or from parallel.py. We import them here for backward compatibility with any
# code that did `from .passes import fan_out, _worker`.
from .parallel import fan_out, _worker  # noqa: F401


def play_model(game, version: str, model: str, site: Path,
               seeds: list[int] | None = None, endpoint: str | None = None,
               token: str | None = None, folder: Path | None = None,
               attempt: int = 1, conversations: bool = True,
               settings: dict[str, Any] | None = None,
               region: int | str = 1, campaign: bool = False) -> dict[str, Any]:
    """Plays one sequential pass of this model over the seed list under this harness."""
    from ...bot.catalogue import load_class

    seeds = seeds or STANDARD_SEEDS
    cls = load_class(harness_path(version))
    # The constructor refuses unknown keys by name.
    bot = cls(seed=0, model=model, endpoint=endpoint, token=token,
              **(settings or {}))
    # The fingerprint is taken here, before play starts.
    stamp = fingerprints(version)
    log = PassLog(version, model, seeds, workers=1, folder=folder,
                  attempt=attempt, memory=cross_run_memory(version),
                  region=region_name(normalise_region(region)) if region != 1 else None)
    # Records what the model was actually sent, beside the decision trace.
    chat = Conversations(log.path.with_name(log.path.stem + CHAT_SUFFIX))
    if conversations:
        chat.watch(bot)
    last = [time.time()]

    # A single bot instance lives for the whole pass. Notes survive on_start and
    # cross between runs. The next pass starts naive because nothing survives the bot.
    #
    # Token counts reset per run via on_start, so they are read per-run in on_run.
    def on_run(row: dict[str, Any], done: int, total: int) -> None:
        now = time.time()
        n = bot.metadata()
        row.update(tokens_in=n.get("tokens_in", 0), tokens_out=n.get("tokens_out", 0),
                   calls=n.get("calls", 0), turns=n.get("turns", 0),
                   fallbacks=n.get("fallbacks", 0), retries=n.get("retries", 0),
                   secs=round(now - last[0], 1))
        # The play order within the pass is needed to interpret memory harnesses.
        row["order"] = done
        if "notebook" in n:
            # The model's notes at this run's end, saved per run to track revision.
            row["notebook"] = n["notebook"]
            row["notes_kept"] = n.get("notes_kept", len(n["notebook"]))
        if "plan" in n:
            # The route committed to at run end, saved per run like the notebook.
            row["plan"] = n["plan"]
        if n.get("run_summary"):
            # What the finished run left for the next one. A harness that writes no
            # summary reports none, and the field is then absent rather than empty.
            row["run_summary"] = n["run_summary"]
        last[0] = now
        log.run(row)

    # The latest observation is kept here for the decided() callback.
    seen: dict[str, Any] = {}

    def looked(obs: dict[str, Any], _steps: int) -> None:
        seen["obs"] = obs
        chat.turn(obs.get("seed", 0), obs.get("steps", 0))

    drawn = [""]

    def decided(e: dict[str, Any]) -> None:
        """Enriches a decision entry with tool calls and map view, then logs it."""
        enriched = enrich_decision(e, bot, seen.get("obs"), drawn)
        chat.flush()
        log.decision(enriched)

    try:
        result = run_benchmark(
            game, bot, bot_name=f"{model} @ {version}", site=site, seeds=seeds,
            category="llm", description=f"model benchmark, harness {version}",
            on_run=on_run, on_decision=decided, on_step=looked,
            region=region, campaign=campaign,
        )
    except BaseException as e:
        # Deliberate stops (SIGTERM, Ctrl-C) are logged as "stopped."
        if isinstance(e, KeyboardInterrupt) or (
                isinstance(e, SystemExit) and e.code in (130, 143)):
            log.stopped(f"{type(e).__name__}: {e.code if isinstance(e, SystemExit) else 'Ctrl-C'}")
        else:
            log.fail(f"{type(e).__name__}: {e}")
        chat.close()
        log.close()
        raise
    one = _as_pass(version, model, seeds, result["runs"], result["game"],
                   result.get("notes") or {}, fingerprint=stamp,
                   region=region_name(normalise_region(region)) if region != 1 else None,
                   settings=settings, site=site)
    # The stamp is recorded explicitly because absolute log paths may not resolve on another host.
    one["stamp"] = log.stamp
    one["log"] = str(log.path)
    one["trace"] = str(log.trace_path)
    chat.close()
    log.done(one)
    log.close()
    return one
