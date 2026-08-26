"""Session management, including what was asked for and whether a pass may be recorded.

Each command invocation gets its own directory containing what was asked for
beside what the command produced. The seed guard that decides whether a pass may
enter the official standings lives here too.
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from ...arena.bench import STANDARD_SEEDS
from .versions import _bench


def session_dir(version: str) -> Path:
    """Creates one directory per command, named by timestamp plus a short random suffix.

    Everything that command writes goes inside, including a log and a decision trace
    for each pass and a record of what was asked for. Results do not live here
    because a result is one file per model with every pass appended.
    """
    import uuid

    # The timestamp provides readability and sort order. The random suffix ensures
    # uniqueness when two commands launch in the same second (parallel containers,
    # shell loops). mkdir(exist_ok=False) is the atomic backstop on suffix collision.
    base = _bench() / version / "logs"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    while True:
        d = base / f"{ts}-{uuid.uuid4().hex[:4]}"
        try:
            d.mkdir(parents=True, exist_ok=False)
            return d
        except FileExistsError:
            continue


def parse_settings(pairs: list[str] | None) -> dict[str, Any]:
    """Converts `--set notes=4` into `{"notes": 4}` for the harness constructor to accept or refuse.

    Nothing is validated here because the harness constructor already refuses
    unknown keys by name. Values are typed by shape (int/float/bool/str).
    """
    out: dict[str, Any] = {}
    for item in pairs or []:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise ValueError(f"--set wants key=value, got {item!r}")
        value = value.strip()
        if value.lower() in ("true", "false"):
            out[key] = value.lower() == "true"
            continue
        for cast in (int, float):
            try:
                out[key] = cast(value)
                break
            except ValueError:
                continue
        else:
            out[key] = value
    return out


def record_command(folder: Path, payload: dict[str, Any]) -> Path:
    """Writes the command's payload (flags, model, endpoint) to command.json.

    The endpoint is recorded because results from different providers are not the
    same measurement. Credential-shaped keys are refused outright to prevent
    accidental token storage.
    """
    banned = {"api_key", "apikey", "token", "fw_token", "key", "secret",
              "password", "authorization"}
    bad = sorted(k for k in payload if k.lower().replace("-", "_") in banned)
    if bad:
        raise ValueError(
            f"refusing to write {', '.join(bad)} into {folder.name}/command.json: "
            f"credentials do not belong in a record of what was measured."
        )
    path = folder / "command.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def records(seeds: list[int]) -> bool:
    """Returns whether a pass over these seeds may be written to `results/`.

    The standard fifty are accepted in any order. Comparing the sorted lists still
    refuses a different set of seeds, a partial list and a list that repeats a seed,
    because the comparison runs element by element.

    Order used to be part of the test, since a harness with cross-run memory plays
    the seeds one after another and the notes accumulate as it goes. Holding the order
    fixed made the position of a run and the identity of its seed the same variable,
    which left every question about learning within a pass unanswerable, so the order
    is now drawn per pass and recorded instead.
    """
    return sorted(seeds) == list(STANDARD_SEEDS)


def play_order(seeds: list[int], order_seed: int | None,
               attempt: int = 1) -> list[int]:
    """Returns the seeds in the order one pass will play them.

    An `order_seed` of None hands the list back untouched, which is what every pass
    recorded before this existed did, and what `--in-seed-order` asks for. A number
    draws a permutation from it, so the pass replays exactly when the same number is
    given again. The attempt number joins the draw, so each repeat of one command
    plays its own order and the difficulty of a position averages out over passes.
    """
    if order_seed is None:
        return list(seeds)
    # Seeded from a string because Random accepts one and derives a stable state from
    # it, which keeps the permutation reproducible across machines.
    return random.Random(f"{order_seed}:{attempt}").sample(list(seeds), len(seeds))
