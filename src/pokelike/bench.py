"""The standard benchmark, so different bots can be compared honestly.

Two things make a result comparable, and both are easy to get wrong:

**The same runs.** Luck dominates a single game. The benchmark uses a fixed seed
list, so every bot faces the identical set of maps, starters and encounters.
Comparing bots on different seeds mostly measures who drew the nicer maps.

**The same game.** The upstream game gets updated, and its filename carries a
content hash. A score from before an update is not comparable with one from
after, so the result file records the hash of the exact bundle that was played.
Without it a leaderboard silently mixes different games.

Results are self-reported: nobody can run everyone else's bot, least of all one
that needs an API key. What makes that acceptable is that a self-contained bot
can be re-run by anyone with a single command, and the result file says exactly
which game and which seeds to reproduce.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import play_run

# The official seed list. Fifty runs is enough to see past the luck without
# taking all afternoon, and it is held well away from the seeds used elsewhere
# in the project so nobody trains on the benchmark by accident.
STANDARD_SEEDS = list(range(10_000, 10_050))

CATEGORIES = ("rules", "rl", "llm", "human", "other")


def bundle_fingerprint(site: Path) -> dict[str, str]:
    """Identifies the exact version of the game that was played."""
    bundle = next(Path(site).glob("js/bundle*.js"), None)
    if bundle is None:
        return {"file": "unknown", "sha256": "unknown"}
    return {
        "file": bundle.name,
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest()[:16],
    }


def summarise(runs: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["score"] for r in runs if r.get("score") is not None]
    if not scores:
        return {"runs": len(runs)}
    return {
        "runs": len(runs),
        "score_mean": round(statistics.mean(scores), 1),
        "score_median": round(statistics.median(scores), 1),
        "score_best": max(scores),
        "score_worst": min(scores),
        "score_stdev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0.0,
        "badges_mean": round(statistics.mean([r.get("badges") or 0 for r in runs]), 2),
        "badges_best": max((r.get("badges") or 0) for r in runs),
        "maps_mean": round(statistics.mean([r.get("maps") or 0 for r in runs]), 2),
        "completed": sum(1 for r in runs if r.get("ending") == "win-screen"),
        "steps_mean": round(statistics.mean([r["steps"] for r in runs]), 1),
    }


def progress_bar(**kw: Any) -> Any:
    """A tqdm bar that also works when nobody is watching a terminal.

    Attached to a terminal, the usual thing: a bar that redraws in place several
    times a second.

    Detached -- `docker compose run -d`, a pipe, nohup -- there is no cursor to
    move. tqdm still writes, but it separates frames with a carriage return and
    never a newline, so the whole run arrives as one enormous line that a log
    reader renders as overlapping garbage or as nothing at all. That is exactly
    what `docker logs` shows.

    So without a tty each frame becomes a whole line, and the refresh drops to
    every ten seconds -- because a bar redrawing ten times a second into a log file
    is thousands of lines saying almost the same thing.
    """
    from tqdm import tqdm

    if sys.stderr.isatty():
        return tqdm(**kw)

    class Lines:
        """tqdm's frames as complete lines, for a log with no cursor."""

        def write(self, data: str) -> None:
            data = data.replace("\r", "").strip()
            if data:
                sys.stderr.write(data + "\n")

        def flush(self) -> None:
            sys.stderr.flush()

    # The caller's own settings win: a `mininterval` passed in is a deliberate
    # choice and must not be overridden by the default for detached runs.
    # Wide, because there is no terminal to wrap against and the fields are the
    # point: at 110 columns tqdm truncates the postfix and eats the token counts.
    return tqdm(**{"file": Lines(), "mininterval": 10.0, "ncols": 200, **kw})


def _tok(n: int) -> str:
    """Token counts short enough to sit in a progress bar without moving it.

    The threshold is 999_500 rather than a million because that is where rounding
    to thousands would print `1000k`, which is a millon spelled badly.
    """
    return f"{n / 1e6:.2f}M" if n >= 999_500 else f"{n / 1000:.0f}k"


def live_fields(obs: dict[str, Any], bot: Any = None,
                so_far: tuple[int, int] | None = None) -> dict[str, Any]:
    """What is worth seeing WHILE a run is still going, for a progress bar.

    Not a log line and not a record: every reading replaces the last one. The
    record is the row written when the run ends.

    Depth comes from the nodes rather than from a field, because the engine has no
    "how long is this map" anywhere -- each node carries a `layer`, so the deepest
    one is the boss and `current`'s layer is how far in the bot has got. That
    answers the question a step count cannot: 34 steps means nothing, layer 6 of 7
    means the gym leader is next.

    `so_far` is what the finished runs already spent, so the token fields read
    `this run / the whole pass`. In and out are separate because output costs
    several times more per token, and one total cannot be turned into a bill.

    No seed here on purpose: tqdm renders numbers through its own formatter and
    turns 10000 into `1e+4`, which is worse than useless. The bar's own counter
    already says which run of how many this is.
    """
    run = obs.get("run") or {}
    m = obs.get("map") or {}
    out: dict[str, Any] = {"badges": run.get("badges", 0)}
    if run.get("map") is not None:
        out["map"] = run["map"]

    nodes = m.get("nodes") or []
    layers = [n.get("layer") for n in nodes if isinstance(n.get("layer"), int)]
    here = next((n for n in nodes if n.get("id") == m.get("current")), None)
    if layers and here is not None and isinstance(here.get("layer"), int):
        out["layer"] = f"{here['layer']}/{max(layers)}"
    elif layers:
        # Between maps, or on a screen that is not the board: the depth is still
        # worth showing, the position is simply not known yet.
        out["layer"] = f"?/{max(layers)}"

    if bot is not None:
        # Read off the bot rather than asked for, so nothing else has to know what
        # an LLM is. `on_start` resets these, so they are THIS run's.
        ti = getattr(bot, "tokens_in", 0) or 0
        to = getattr(bot, "tokens_out", 0) or 0
        if ti or to:
            if so_far:
                out["in"] = f"{_tok(ti)}/{_tok(so_far[0] + ti)}"
                out["out"] = f"{_tok(to)}/{_tok(so_far[1] + to)}"
            else:
                out["in"], out["out"] = _tok(ti), _tok(to)
        fell = getattr(bot, "fallbacks", 0) or 0
        if fell:
            out["fell"] = fell
        notes = getattr(bot, "notebook", None)
        if notes is not None:
            out["notes"] = len(notes)
    return out


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
    """Plays the seed list and returns the result document."""
    from . import __version__

    seeds = seeds or STANDARD_SEEDS
    runs: list[dict[str, Any]] = []

    bar = progress_bar(iterable=seeds, desc=f"bench {bot_name}", unit="run",
                       leave=True)
    for seed in bar:
        # Live, while the run is still going. Without this the bar sits at the
        # same number for one to three minutes with nothing to say whether the bot
        # is making progress or stuck on a wedged screen -- and on a fifty-seed
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
        def decided(entry, _seed=seed):
            on_decision({"seed": _seed, **entry})

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
        "notes": getattr(bot, "notes", lambda: {})(),
    }


def save(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return path


def format_result(result: dict[str, Any]) -> str:
    s = result["summary"]
    g = result["game"]
    return "\n".join([
        "",
        "=" * 60,
        f"  {result['bot']}   [{result['category']}]",
        "=" * 60,
        f"  runs            {s.get('runs')}",
        f"  score mean      {s.get('score_mean')}   (stdev {s.get('score_stdev')})",
        f"  score median    {s.get('score_median')}",
        f"  score range     {s.get('score_worst')} .. {s.get('score_best')}",
        f"  badges mean     {s.get('badges_mean')}   best {s.get('badges_best')}",
        f"  maps mean       {s.get('maps_mean')}",
        f"  runs completed  {s.get('completed')}",
        f"  steps mean      {s.get('steps_mean')}",
        "",
        f"  game bundle     {g['file']}  (sha256 {g['sha256']})",
    ])
