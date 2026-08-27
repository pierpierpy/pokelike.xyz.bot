"""This module computes the repo's canonical directory paths once.

The `shared/` package sits at a fixed depth under the repo root
(`src/pokelike/shared/`), so this file counts parent directories once and
every caller imports the result instead of recomputing the path from its own
`__file__`.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOTS = ROOT / "bots"

# The benchmark directory answers to POKELIKE_BENCH so a caller in another process can
# be pointed somewhere else. A test that runs the CLI in a subprocess cannot reach the
# module with a monkeypatch, and `model board` draws its charts into this directory, so
# without the override a test run rewrites the tracked images.
BENCH = Path(os.environ.get("POKELIKE_BENCH") or (ROOT / "llm-bench"))
