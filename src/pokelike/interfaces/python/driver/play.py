"""Run one or more games with a bot.

Returns run result dicts with decision traces included.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....core.runner import play_run
from .session import SITE, session


def play(bot: Any, seed: int = 1, max_steps: int = 400, watch: bool = False,
         on_decision=None, site: Path | str = SITE,
         region: int | str = 1) -> dict[str, Any]:
    """Play one run with a bot and return the result dict, including the decision trace.

    Uses the same play_run the CLI and the benchmark use.
    """
    with session(site=site, watch=watch) as game:
        return play_run(game, bot, seed, max_steps=max_steps, on_decision=on_decision,
                        region=region)


def evaluate(bot: Any, seeds, max_steps: int = 400,
             site: Path | str = SITE,
             region: int | str = 1) -> list[dict[str, Any]]:
    """Play a bot over several seeds in one browser session. Returns one row per run.
    """
    with session(site=site) as game:
        return [play_run(game, bot, s, max_steps=max_steps, region=region) for s in seeds]
