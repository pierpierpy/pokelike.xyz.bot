"""The subprocess entry point for one worker of a parallel pass.

In: the flags `fan_out` passes on the command line (`--worker --harness V --model
ID --port N --seeds a,b,c`). Out: the process exit code, with one JSON row per
finished seed on stdout for the parent to collect.

Its own module, and deliberately NOT imported by the package `__init__`. A module
that the package already imported cannot then be run with `python -m` without
Python importing it a second time under the name `__main__`, which it warns about
and which would leave two copies of the same module's globals in one process. This
file is the only thing the spawn names, so that never happens.
"""
from __future__ import annotations

from .parallel import _worker

if __name__ == "__main__":
    raise SystemExit(_worker())
