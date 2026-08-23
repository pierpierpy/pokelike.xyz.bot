"""The subprocess entry point for one worker of a parallel pass.

This module exists as a separate file (not imported by __init__) so it can be
run with `python -m` without causing a double-import of the package.
"""
from __future__ import annotations

from .parallel import _worker

if __name__ == "__main__":
    raise SystemExit(_worker())
