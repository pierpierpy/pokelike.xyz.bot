"""Low-level download and cleanup helpers for the offline copy.

In: a relative path and a root directory. Out: the file on disk (or False).
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

from .signatures import SIGNATURES, _valid_content

UPSTREAM = "https://pokelike.xyz"

# File paths contain no spaces, so they can be found with a regex over the raw
# bundle: nothing needs de-obfuscating for this.
RE_ASSET = re.compile(r"""["'](/?(?:img|audio|style|js|fonts?)/[\w\-./]+?\.\w{2,5})["']""")
RE_HTML_REF = re.compile(r"""(?:src|href)=["']([^"'#?]+\.(?:js|css|png|svg|ico|webmanifest))["']""")
RE_CSS_URL = re.compile(r"""url\(["']?([^"')]+?\.\w{2,5})["']?\)""")


def _log(*a) -> None:
    """Print immediately: without a flush, progress is invisible when redirected."""
    print(*a, flush=True)


def _fetch(path: str, root: Path) -> bool:
    """Downloads a relative path into the root.

    In: the URL-relative path and the local root. Out: True if it now exists
    and is valid.
    """
    rel = path.lstrip("/")
    dest = root / rel
    if dest.is_file() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(
            f"{UPSTREAM}/{rel}", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200:
                return False
            data = r.read()
    except Exception:
        return False
    if not _valid_content(data, dest.suffix):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def clean(root: Path, log=_log) -> int:
    """Deletes files whose content does not match their extension.

    In: the site root directory. Out: the number of files removed.
    """
    removed = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            head = p.open("rb").read(8)
        except OSError:
            continue
        if not _valid_content(head, p.suffix):
            p.unlink()
            removed += 1
    log(f"  removed {removed} invalid files")
    return removed
