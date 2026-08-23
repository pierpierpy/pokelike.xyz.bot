"""The standard benchmark: plays the fixed 50-seed list and records the result.

Comparability requires two things: the same seeds (so luck cancels out) and the
same game bundle (so an upstream update does not silently mix different games).
The result file records both.
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
