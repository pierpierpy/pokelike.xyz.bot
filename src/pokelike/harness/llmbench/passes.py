"""Running a pass: one model over the seed list, sequentially.

A pass is a complete run of the standard seeds under one harness with one model.
Sequential when the harness carries cross-run memory (runs depend on each other).
For parallel execution (independent seeds, multiple subprocesses), see parallel.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ...arena.bench import STANDARD_SEEDS, run_benchmark
from .passlog import PassLog
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
               attempt: int = 1,
               settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """One pass: this model over the seed list, under this harness.

    In: a Game instance, version, model, site path, optional seeds/credentials/
    folder/attempt/settings. Out: the assembled pass dict.
    """
    from ...bot.catalogue import load_class

    seeds = seeds or STANDARD_SEEDS
    cls = load_class(harness_path(version))
    # Straight to the constructor, which refuses what it does not know by name. A
    # setting silently ignored is worse than one that does not exist, because the
    # pass then answers a question nobody asked.
    bot = cls(seed=0, model=model, endpoint=endpoint, token=token,
              **(settings or {}))
    # Taken now, against the code about to play, not at the end against whatever
    # is on disk by then.
    stamp = fingerprints(version)
    log = PassLog(version, model, seeds, workers=1, folder=folder,
                  attempt=attempt, memory=cross_run_memory(version))
    last = [time.time()]

    # One bot for the whole pass, which is what resets a memory harness: notes
    # survive `on_start` and so cross between runs, and nothing survives the bot,
    # so the next pass starts naive. Nothing to reset by hand, and nothing that
    # could be forgotten, which is why it is arranged this way rather than with a
    # reset call.

    # Token counts are per run: `on_start` resets them, so reading notes() once at
    # the end would report only the last of fifty runs. `on_run` hands back the row
    # itself, so each one carries what that run actually spent.
    def on_run(row: dict[str, Any], done: int, total: int) -> None:
        now = time.time()
        n = bot.metadata()
        row.update(tokens_in=n.get("tokens_in", 0), tokens_out=n.get("tokens_out", 0),
                   calls=n.get("calls", 0), turns=n.get("turns", 0),
                   fallbacks=n.get("fallbacks", 0), retries=n.get("retries", 0),
                   secs=round(now - last[0], 1))
        # Which run of the pass this was. Rows are stored in seed order, but a
        # memory harness is only interpretable in the order it was PLAYED: the
        # tenth run had nine runs' worth of notes behind it. Recorded for every
        # version, because it costs one integer and its absence cannot be
        # reconstructed afterwards.
        row["order"] = done
        if "notebook" in n:
            # What the model believed at the end of this run, saved with the run
            # rather than once at the end of the pass, so a lesson that was learned
            # and later revised away is still in the record.
            row["notebook"] = n["notebook"]
            row["notes_kept"] = n.get("notes_kept", len(n["notebook"]))
        if "plan" in n:
            # The route it had committed to when the run ended. Per run, like the
            # notebook, and for the same reason: the interesting object is how it
            # changed, not where it landed.
            row["plan"] = n["plan"]
        last[0] = now
        log.run(row)

    # The observation the run loop is about to hand the bot, kept for exactly as
    # long as it takes to write the decision that came out of it. `run_benchmark`
    # already calls this before every decision for the progress bar.
    seen: dict[str, Any] = {}

    def looked(obs: dict[str, Any], _steps: int) -> None:
        seen["obs"] = obs

    drawn = [""]

    def decided(e: dict[str, Any]) -> None:
        """One decision, with what the bot did to reach it and what it was looking at.

        The tool calls come from the BOT and not from the runner: the runner sees a
        bot return an index, and everything between the question and the answer happens
        inside `choose`. Every harness has them, its own list where it keeps one and a
        wrapper around `run_tool` where it does not.

        The map is drawn with the SHARED renderer, not the harness's frozen copy.
        This is the log, not the prompt: it says where the run was, and the layer
        picture is the same in every copy anyway. What the model actually read is
        fixed by the harness and reproducible from it.
        """
        extra: dict[str, Any] = {}
        # Every harness keeps this list. The one that did not was v0, and the
        # answer was to give it one rather than to guess from outside: `play` and
        # `set_lead` never reach `run_tool`, so a wrapper around that method could
        # not see the decision itself.
        called = bot.tool_calls_made()
        if called:
            extra["tools"] = called
        obs = seen.get("obs")
        if obs and (obs.get("map") or {}).get("nodes"):
            from ...core import render

            picture = render.map_view(obs["map"])
            if picture and picture != drawn[0]:
                extra["map_view"] = picture
                drawn[0] = picture
        log.decision({**e, **extra} if extra else e)

    try:
        result = run_benchmark(
            game, bot, bot_name=f"{model} @ {version}", site=site, seeds=seeds,
            category="llm", description=f"model benchmark, harness {version}",
            on_run=on_run, on_decision=decided, on_step=looked,
        )
    except BaseException as e:
        log.fail(f"{type(e).__name__}: {e}")
        log.close()
        raise
    one = _as_pass(version, model, seeds, result["runs"], result["game"],
                   result.get("notes") or {}, fingerprint=stamp)
    # Named explicitly, not only implied by the paths below: those are absolute
    # and were written inside the container, so `/app/...` is a directory that does
    # not exist on the host reading the result. The stamp is the portable half.
    one["stamp"] = log.stamp
    one["log"] = str(log.path)
    one["trace"] = str(log.trace_path)
    log.done(one)
    log.close()
    return one
