"""Writing and reading bot results.

In: a bot name and a result dict. Out: the result.json file on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...bot.catalogue import BOTS, folder, slugify
from .artifact import KINDS, fingerprint


def record_result(name: str, result: dict[str, Any], bot: Any,
                  root: Path | None = None) -> Path:
    """Writes `result.json` into the bot's own folder, artifacts included.

    In: the bot name, the result dict, and the bot instance. Out: the path to
    the bot folder.
    """
    d = folder(name, root)
    if not (d / "bot.py").is_file():
        raise FileNotFoundError(
            f"{d} is not a bot: no bot.py.\n"
            f"Create one with:  uv run pokelike bot new {slugify(name)}"
        )

    declared = list(getattr(bot, "artifacts", lambda: [])() or [])
    for a in declared:
        if a.kind not in KINDS:
            print(f"  note: artifact '{a.name}' has an unrecognised kind "
                  f"'{a.kind}', archiving it anyway")
    manifest = [a.write_into(d / "artifacts") for a in declared]

    document = {
        **result,
        "bot": slugify(name),
        # Written LAST, over the artifacts as they now are on disk.
        "fingerprint": fingerprint(d),
        "artifacts": manifest,
    }
    (d / "result.json").write_text(json.dumps(document, indent=1), encoding="utf-8")
    return d


def load_results(root: Path | None = None) -> list[dict[str, Any]]:
    """Reads every result.json under the bots directory.

    In: an optional root path. Out: a list of result dicts with staleness checks.
    """
    base = Path(root) if root else BOTS
    if not base.is_dir():
        return []
    out = []
    for f in sorted(base.glob("*/result.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  warning: {f} is not valid JSON, skipping")
            continue
        # The folder IS the name. A `bot` field left over from somewhere else
        # would let a row claim to be a bot it is not.
        r["bot"] = f.parent.name
        # Recomputed every time it is read, so a row cannot claim a score for
        # code that has since been edited without saying so.
        #
        # A result with NO fingerprint is not clean, it is unchecked: it
        # predates the mechanism, or was hand-written. Reported separately rather
        # than folded into either bucket: calling it stale would be a claim we
        # cannot support, and calling it fine would be the silence the
        # fingerprint exists to prevent.
        r["unverified"] = not r.get("fingerprint")
        r["stale"] = bool(r.get("fingerprint")) and r["fingerprint"] != fingerprint(f.parent)
        out.append(r)
    return out
