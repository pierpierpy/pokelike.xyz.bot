"""Where the repo's real directories are, computed once.

Four independent call sites used to count parent directories from their own
`__file__` to find `bots/` or `llm-bench/`, each with its own count. Moving a
file one directory deeper (exactly what happened during the src/ split) broke
one count and silently left the others wrong. `shared/` sits at a fixed depth
under the repo root (`src/pokelike/shared/`), so this file counts once, here,
and every caller imports the result instead of recomputing it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOTS = ROOT / "bots"
BENCH = ROOT / "llm-bench"
