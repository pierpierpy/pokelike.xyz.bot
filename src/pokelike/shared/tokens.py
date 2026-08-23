"""This module provides one way to shorten a token count for display.

`arena/bench/progress.py` (the live progress bar), `harness/watch/dashboard.py`
(a single pass's panel), and `harness/watch/overview.py` (every running pass)
each need to print the same kind of number small enough to fit a line. None of
the three imports from another; all three import from this module.
"""

from __future__ import annotations


def tok(n: int) -> str:
    """This function formats a token count as a short string like '35k' or '1.20M'."""
    return f"{n / 1e6:.2f}M" if n >= 999_500 else f"{n / 1000:.0f}k"
