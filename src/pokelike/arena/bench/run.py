"""The benchmark loop: plays the seed list and collects results.

In: a game, a bot, and a seed list. Out: the complete result document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...core.runner import play_run
from .progress import _tok, live_fields, progress_bar
from .seeds import STANDARD_SEEDS, bundle_fingerprint, summarise


def run_benchmark(
    game,
    bot,
    bot_name: str,
    site: Path,
    seeds: list[int] | None = None,
    author: str = "",
    category: str = "other",
    description: str = "",
    max_steps: int = 400,
    on_run=None,
    on_step=None,
    on_decision=None,
) -> dict[str, Any]:
    """Plays the seed list and returns the result document.

    In: the game instance, bot instance, bot name, site path, and optional
    callbacks. Out: the full result dict ready for record_result().
    """
    from ... import __version__

    seeds = seeds or STANDARD_SEEDS
    runs: list[dict[str, Any]] = []

    bar = progress_bar(iterable=seeds, desc=f"bench {bot_name}", unit="run",
                       leave=True)
    for seed in bar:
        # Live, while the run is still going. Without this the bar sits at the
        # same number for one to three minutes with nothing to say whether the bot
        # is making progress or stuck on a wedged screen, and on a fifty-seed
        # LLM pass that is most of an hour of no information at all. Written into
        # the bar rather than printed: it is the state of one run, which is
        # replaced by the next reading rather than worth a line of its own.
        def live(obs, steps, _seed=seed):
            # What the finished runs already spent, so the bar can show this run
            # against the pass. Summed here rather than kept in a counter: the rows
            # are the only place tokens are recorded, and a second tally would be a
            # second thing to keep in step with them.
            spent = (sum(r.get("tokens_in") or 0 for r in runs),
                     sum(r.get("tokens_out") or 0 for r in runs))
            bar.set_postfix({"step": steps, **live_fields(obs, bot, spent)})
            if on_step:
                on_step(obs, steps)

        # The seed is injected here rather than added to the trace entry itself:
        # `play_run` plays ONE run and has no reason to repeat which one on every
        # line, but a file collecting fifty runs does.
        #
        # The token counters come along for the same reason. They are the bot's, and
        # `on_start` resets them, so they are THIS run's cumulative: everything
        # else (what one turn cost, what the pass has cost) is arithmetic on top,
        # and is done by whoever writes the file.
        def decided(entry, _seed=seed):
            on_decision({
                "seed": _seed,
                "run_in": getattr(bot, "tokens_in", 0) or 0,
                "run_out": getattr(bot, "tokens_out", 0) or 0,
                **entry,
            })

        full = play_run(game, bot, seed, max_steps=max_steps, on_step=live,
                        on_decision=decided if on_decision else None)
        # The heavy fields (final state, full team) are for callers who want
        # them; a result file keeps one compact row per run.
        row = {k: full[k] for k in
               ("seed", "steps", "score", "badges", "maps", "kos", "faints", "ending",
                "stalled")}
        runs.append(row)
        done = [r["score"] for r in runs if r["score"] is not None]
        bar.set_postfix(score=row["score"],
                        mean=round(sum(done) / len(done), 1) if done else None)
        if on_run:
            on_run(row, len(runs), len(seeds))

    return {
        "bot": bot_name,
        "author": author,
        "category": category,
        "description": description,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pokelike_version": __version__,
        "game": bundle_fingerprint(site),
        "seeds": seeds,
        "summary": summarise(runs),
        "runs": runs,
        "notes": getattr(bot, "metadata", lambda: {})(),
    }
