"""The leaderboard: reading what each bot scored, and writing what one scored.

A bot is a folder under `bots/`, and its measurement lives in that same folder:

    bots/<name>/
    +-- bot.py        the code that ran
    +-- artifacts/    the weights, prompts or tables it needs
    +-- result.json   the benchmark, with a fingerprint of both

`Artifact` is a frozen import path: the frozen harnesses under
llm-bench/*/harness/bot.py and the submitted bots in bots/* import it from
exactly `pokelike.arena.leaderboard`.
"""

from .artifact import Artifact, KINDS, fingerprint, sha256_of
from .record import load_results, record_result
from .table import (
    README_BEGIN,
    README_END,
    as_markdown,
    build_index,
    format_table,
    render_readme,
)

__all__ = [
    "Artifact",
    "KINDS",
    "fingerprint",
    "sha256_of",
    "record_result",
    "load_results",
    "build_index",
    "format_table",
    "as_markdown",
    "render_readme",
    "README_BEGIN",
    "README_END",
]
