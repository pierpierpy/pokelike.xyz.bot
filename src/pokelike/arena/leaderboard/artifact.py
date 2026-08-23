"""This module defines the Artifact dataclass and the fingerprint that ties a result to its code.

The fingerprint is a sha256 over ``bot.py`` and every file in ``artifacts/``.
The ``pokelike bot board`` command compares the current hash against the recorded
one and marks stale rows.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Known artifact kinds, so a reader knows what each file is without opening it.
KINDS = {
    "weights-json": "a trained policy, as JSON",
    "weights-remote": "weights hosted elsewhere, with a url and a sha256",
    "config": "how it was trained or configured",
    "prompt": "the text given to a language model",
    "notes": "anything else worth keeping beside the result",
}


@dataclass
class Artifact:
    """An Artifact represents something a bot needs, archived beside the bot.

    Provide ``path`` to copy a file, ``data`` to write JSON, or ``text`` to
    write prose (such as a prompt). A bot declares these from ``artifacts()``,
    and the benchmark stores them.
    """

    name: str
    kind: str
    description: str = ""
    path: Path | None = None
    data: Any = None
    text: str | None = None
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def write_into(self, folder: Path) -> dict[str, Any]:
        """Writes this artifact into the given folder and returns the manifest entry."""
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / self.name
        if self.path is not None:
            # When path == target (the bot's folder is already the archive), skip the copy.
            if Path(self.path).resolve() != target.resolve():
                shutil.copy2(self.path, target)
            elif not target.is_file():
                raise FileNotFoundError(f"artifact '{self.name}' is missing at {target}")
        elif self.data is not None:
            target.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        elif self.text is not None:
            target.write_text(self.text, encoding="utf-8")
        elif self.url is None:
            raise ValueError(
                f"artifact '{self.name}' has no path, data, text or url"
            )
        entry = {
            "name": self.name, "kind": self.kind, "description": self.description,
            **({"url": self.url} if self.url else {}), **self.extra,
        }
        if target.is_file():
            entry["bytes"] = target.stat().st_size
            entry["sha256"] = sha256_of(target)
        return entry


# ---------------------------------------------------------------- fingerprint


def sha256_of(path: Path) -> str:
    """Returns the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def fingerprint(bot_dir: Path) -> str:
    """Returns a single hash over bot.py and every file in artifacts/.

    Each file is hashed together with its relative path, so renaming a file
    changes the fingerprint. The actual logic lives in
    ``pokelike.shared.fingerprint.code_fingerprint``, and
    ``utils/refingerprint.py`` imports it from there as well.
    """
    from ...shared.fingerprint import code_fingerprint
    return code_fingerprint(bot_dir)
