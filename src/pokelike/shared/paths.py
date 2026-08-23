"""This module computes the repo's canonical directory paths once.

The `shared/` package sits at a fixed depth under the repo root
(`src/pokelike/shared/`), so this file counts parent directories once and
every caller imports the result instead of recomputing the path from its own
`__file__`.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOTS = ROOT / "bots"
BENCH = ROOT / "llm-bench"
