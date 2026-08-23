"""Builds the fingerprint of a played run.

This is the heart of the regression suite. The fingerprint holds only data that
comes from the game engine (screen ids, node types, Pokemon names, and scores),
never text we write ourselves. That is deliberate because our own wording can be
translated or reworded, while the engine's data cannot change without a real
behavioural regression.

So the same golden file stays valid across a full translation of this codebase,
and any difference in the golden file is a genuine bug.

The actual replay logic (the policies, `_stable_action`, the play loop, `CASES`)
lives in `pokelike.shared.fingerprint`, since `src/pokelike/harness/llmbench/`'s
`behaviour` check plays the exact same replay for the exact same reason. This
module re-exports it under the names this test suite and `record_golden.py`
already use, so the golden file and the behaviour hash can never quietly
disagree about what "stable" means.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokelike.shared.fingerprint import CASES, replay as fingerprint  # noqa: E402

GOLDEN = Path(__file__).parent / "golden" / "runs.json"


def load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def save_golden(data: dict[str, Any]) -> None:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
