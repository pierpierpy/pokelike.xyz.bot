"""Writing and reading bot results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...bot.catalogue import BOTS, folder, slugify
from .artifact import KINDS, fingerprint


def record_result(name: str, result: dict[str, Any], bot: Any,
                  root: Path | None = None) -> Path:
    """Writes `result.json` and artifacts into the bot's folder."""
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
        # Written after the artifacts, so the fingerprint covers their final state.
        "fingerprint": fingerprint(d),
        "artifacts": manifest,
    }
    (d / "result.json").write_text(json.dumps(document, indent=1), encoding="utf-8")
    return d


def load_results(root: Path | None = None) -> list[dict[str, Any]]:
    """Reads every result.json under the bots directory, adding staleness flags."""
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
        # The folder name is authoritative; ignore any `bot` field in the file.
        r["bot"] = f.parent.name
        # Recomputed on every read so edits after a benchmark are detected.
        #
        # A missing fingerprint is "unverified", not "stale": the result
        # predates the mechanism or was hand-written.
        r["unverified"] = not r.get("fingerprint")
        r["stale"] = bool(r.get("fingerprint")) and r["fingerprint"] != fingerprint(f.parent)
        out.append(r)
    return out
