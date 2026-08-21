"""The standard benchmark, so different bots can be compared honestly.

Two things make a result comparable, and both are easy to get wrong:

**The same runs.** Luck dominates a single game. The benchmark uses a fixed seed
list, so every bot faces the identical set of maps, starters and encounters.
Comparing bots on different seeds mostly measures who drew the nicer maps.

**The same game.** The upstream game gets updated, and its filename carries a
content hash. A score from before an update is not comparable with one from
after, so the result file records the hash of the exact bundle that was played.
Without it a leaderboard silently mixes different games.
"""

from .progress import _tok, live_fields, progress_bar
from .report import format_result, save
from .run import run_benchmark
from .seeds import CATEGORIES, STANDARD_SEEDS, bundle_fingerprint, summarise

__all__ = [
    "STANDARD_SEEDS",
    "CATEGORIES",
    "bundle_fingerprint",
    "summarise",
    "progress_bar",
    "_tok",
    "live_fields",
    "run_benchmark",
    "save",
    "format_result",
]
