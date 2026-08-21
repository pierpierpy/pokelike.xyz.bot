"""The Artifact dataclass and the fingerprint that ties a result to its code.

In: a bot directory. Out: a hex digest over bot.py and artifacts/.

WHAT THE FINGERPRINT IS FOR
A score means nothing without the code it came from. `result.json` records a
sha256 over `bot.py` and every artifact, so a result and the thing that produced
it cannot drift apart unnoticed: `pokelike bot board` says `stale` beside any
row whose files have changed since it was measured.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# What an artifact is FOR, so a reader knows what they are looking at without
# opening it. Anything else is archived too, with a note.
KINDS = {
    "weights-json": "a trained policy, as JSON",
    "weights-remote": "weights hosted elsewhere, with a url and a sha256",
    "config": "how it was trained or configured",
    "prompt": "the text given to a language model",
    "notes": "anything else worth keeping beside the result",
}


@dataclass
class Artifact:
    """Something a bot needs, archived beside it.

    Give it `path` to copy a file, `data` to write a JSON document, or `text`
    to write it out as it is. A bot declares these from `artifacts()`, and the
    benchmark stores them.

    `text` exists because a prompt is prose. Putting one through `data` writes a
    JSON string, escapes every newline, and produces a prompt.md nobody can
    read, which is the opposite of why it is archived. The LLM harness had
    been passing `text=` to a dataclass with no such field since it was written,
    and nothing noticed because artifacts() is only called by a complete
    benchmark and no LLM bot had ever finished one.
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
        """Writes this artifact into the given folder.

        In: the target folder. Out: the manifest entry dict.
        """
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / self.name
        if self.path is not None:
            # A bot's artifacts already live in its own folder, so "archiving"
            # them means copying a file onto itself, which shutil refuses. It
            # is not an error: the file IS the artifact and it is already where
            # it belongs. It only became reachable when bots stopped being
            # copied into an archive and started being the archive.
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
    """Hashes a single file with SHA-256.

    In: the file path. Out: the hex digest.
    """
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def fingerprint(bot_dir: Path) -> str:
    """One hash over the bot's code and everything it carries.

    In: the bot directory. Out: the hex digest over bot.py and artifacts/.

    Covers `bot.py` and every file under `artifacts/`, each hashed with its name
    so that renaming a file changes the fingerprint too. This is what makes a
    recorded score checkable: re-hash the folder, compare, and you know whether
    the row still describes what is on disk.
    """
    h = hashlib.sha256()
    files = [bot_dir / "bot.py", *sorted((bot_dir / "artifacts").glob("**/*"))]
    for f in files:
        if not f.is_file():
            continue
        h.update(str(f.relative_to(bot_dir)).encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()
