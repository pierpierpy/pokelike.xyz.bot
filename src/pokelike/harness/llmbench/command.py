"""Session management: what was asked for, and whether it may be recorded.

One directory per command invocation, with what was asked for beside what it
produced. The seed guard that decides whether a pass's results may enter the
official table lives here too: it is a question about the command, not about
what came out of it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ...arena.bench import STANDARD_SEEDS
from .versions import _bench


def session_dir(version: str) -> Path:
    """One directory per command, named for the moment it was launched.

    Everything that command writes goes inside: a log and a decision trace for
    each pass, and what was asked for. Flat files named by model and timestamp
    could not answer "which of these twelve belong together" -- with `--models a,b
    --repeat 3` there were six pairs loose in one directory and only the clock to
    guess by.

    `ls -t` therefore lists your commands, newest first, and
    `tail -f logs/<stamp>/*.log` follows exactly one command and nothing else.

    Results deliberately do NOT live here. A result is one file per model with
    every pass appended, because it is the comparable record: ten commands over
    three days build up one model's history, and splitting it by invocation would
    destroy the only thing it is for.
    """
    import uuid

    # One command = one directory. The timestamp is kept because it is readable
    # and sorts (`ls -t` lists your commands in order), but uniqueness must NOT
    # rest on it: two commands launched in the same second (parallel containers,
    # a shell loop) would otherwise share a directory and a command.json and blur
    # together in `model watch`. A short random suffix makes the name unique by
    # construction; mkdir(exist_ok=False) is the atomic backstop on the ~1-in-65k
    # chance two draw the same four hex in the same second.
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
    """`--set notes=4` into `{"notes": 4}`, for the harness to accept or refuse.

    WHY THIS RATHER THAN A FLAG EACH. The flags every benchmark needs are the
    same handful: which harness, which model, how many seeds, how many workers,
    where to send the request. What ONE harness needs is its own business, and a
    named flag for it means this file, the worker, the fan-out and the parser all
    learn a word that means nothing to any other version. `notes` was exactly
    that: four places threading one integer that only v4 can read.

    Nothing is validated here on purpose. The harness constructor already refuses
    what it does not know, by name, and it is the only thing that knows.

    Values are typed by shape, since a command line has only strings and
    `notes="4"` would be a string where a number belongs.
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
    """What was asked for, beside what it produced.

    The one thing nothing wrote down before: come back to a finished sweep three
    hours later and the flags it ran with were gone, so a surprising number could
    not be traced to how it was asked for.

    The endpoint is written because a row measured against one provider is not the
    same measurement as against another, and that is worth knowing later. A token is
    worth nothing later and is a liability forever, so this REFUSES to write one
    rather than trusting every future caller to leave it out. The check is on the
    keys, not on the values: guessing at the shape of a secret is how secrets get
    written, while a field called `api_key` has no business here whatever it holds.
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
    """Whether a pass over these seeds may be written to `results/`.

    Only the standard fifty, and compared BY VALUE. Length is not enough: fifty
    seeds of somebody's own choosing would otherwise be recorded, and the row would
    sit in the table looking exactly like one that is comparable to every other.
    That is the one mistake this file exists to prevent, so it is a function with a
    test rather than a comparison inlined at the one place that happens to need it.

    Order counts too, deliberately. Under a harness that carries the model's notes
    from one run to the next, the order the seeds were played in is part of what was
    measured, so the same fifty seeds shuffled are not the same measurement.
    """
    return list(seeds) == list(STANDARD_SEEDS)
