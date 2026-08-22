"""The benchmark loop: plays the seed list and collects results.

In: a game, a bot, and a seed list. Out: the complete result document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...core.runner import play_campaign, play_run
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
    region: int | str = 1,
    campaign: bool = False,
) -> dict[str, Any]:
    """Plays the seed list and returns the result document.

    In: the game instance, bot instance, bot name, site path, and optional
    callbacks. Out: the full result dict ready for record_result().
    """
    from ... import __version__
    from ...core.browser import region_name as _rname, normalise_region

    seeds = seeds or STANDARD_SEEDS
    runs: list[dict[str, Any]] = []
    region_int = normalise_region(region)
    rname = _rname(region_int)

    bar = progress_bar(iterable=seeds, desc=f"bench {bot_name}", unit="run",
                       leave=True)
    for seed in bar:
        def live(obs, steps, _seed=seed):
            spent = (sum(r.get("tokens_in") or 0 for r in runs),
                     sum(r.get("tokens_out") or 0 for r in runs))
            bar.set_postfix({"step": steps, **live_fields(obs, bot, spent)})
            if on_step:
                on_step(obs, steps)

        def decided(entry, _seed=seed):
            on_decision({
                "seed": _seed,
                "run_in": getattr(bot, "tokens_in", 0) or 0,
                "run_out": getattr(bot, "tokens_out", 0) or 0,
                **entry,
            })

        if campaign:
            full = play_campaign(game, bot, seed, max_steps=max_steps,
                                 on_step=live,
                                 on_decision=decided if on_decision else None)
            row = {
                "seed": seed,
                "steps": full.get("steps", 0),
                "score": None,
                "badges": full.get("badges", 0),
                "maps": 0,
                "kos": 0,
                "faints": 0,
                "ending": full.get("ending"),
                "stalled": False,
                "regions_played": full.get("regions_played", 0),
                "regions_cleared": full.get("regions_cleared", 0),
                "region": "all",
            }
        else:
            full = play_run(game, bot, seed, max_steps=max_steps, on_step=live,
                            on_decision=decided if on_decision else None,
                            region=region_int)
            row = {k: full[k] for k in
                   ("seed", "steps", "score", "badges", "maps", "kos", "faints", "ending",
                    "stalled")}
            row["region"] = full.get("region") or rname

        runs.append(row)
        done = [r["score"] for r in runs if r["score"] is not None]
        bar.set_postfix(score=row.get("score"),
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
        "region": "all" if campaign else rname,
        "game": bundle_fingerprint(site),
        "seeds": seeds,
        "summary": summarise(runs),
        "runs": runs,
        "notes": getattr(bot, "metadata", lambda: {})(),
    }
