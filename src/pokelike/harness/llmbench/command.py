"""Session management, including what was asked for and whether a pass may be recorded.

Each command invocation gets its own directory containing what was asked for
beside what the command produced. The seed guard that decides whether a pass may
enter the official standings lives here too.
"""

from __future__ import annotations

import json
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

    Only the standard fifty are accepted, compared by value and order. Order
    matters because a harness with cross-run memory plays the seeds sequentially,
    so the order is part of the measurement.
    """
    return list(seeds) == list(STANDARD_SEEDS)
