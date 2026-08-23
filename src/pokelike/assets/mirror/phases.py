"""The five build phases that produce the offline copy of the game.

1. STATIC: index.html, its CSS/JS, and every path named in the bundle.
2. NUMBERED: badges and map backgrounds addressed by number.
3. SLUG: URLs built at runtime as prefix + id + ".png".
4. PLAYED: plays a few runs, downloading what the game asks for.
5. VERIFY: replays offline, counts what is missing, repairs, re-checks.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .fetch import (
    RE_ASSET,
    RE_CSS_URL,
    RE_HTML_REF,
    UPSTREAM,
    _fetch,
    _log,
    clean,
)

# Folders whose URLs the game builds as prefix + slug + ".png".
# The slugs never appear as a complete path in the bundle, so they must be
# tried one at a time.
SLUG_FOLDERS = (
    "img/sprites/items/",
    "img/sprites/trainers/",
    "img/sprites/badges/",
    "img/sprites/g1/", "img/sprites/g2/", "img/sprites/g3/", "img/sprites/g4/",
)
RE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Folders whose URLs are prefix + NUMBER + ".png" (badges, map backgrounds).
# The slug search only finds word-shaped names, so numbered files need their
# own pass.
NUMBERED_FOLDERS = (
    "img/sprites/badges/",
    "img/maps/g1/", "img/maps/g2/", "img/maps/g3/", "img/maps/g4/",
)
MAX_NUMBER = 60


def phase_static(root: Path, log=_log) -> dict[str, int]:
    """Downloads index.html, what it references, and the assets named in the bundle."""
    root.mkdir(parents=True, exist_ok=True)

    if not _fetch("index.html", root):
        raise RuntimeError("cannot download index.html from " + UPSTREAM)
    html = (root / "index.html").read_text(encoding="utf-8", errors="replace")

    paths: set[str] = set(RE_HTML_REF.findall(html))
    paths |= {"favicon.svg", "manifest.webmanifest", "privacy.html"}

    # The bundle filename carries a content hash: it changes with every release.
    bundle = next((p for p in paths if p.startswith("js/bundle")), None)
    if bundle is None:
        raise RuntimeError("cannot find the bundle inside index.html")
    log(f"  bundle: {bundle}")

    for p in sorted(paths):
        _fetch(p, root)

    bundle_text = (root / bundle).read_text(encoding="utf-8", errors="replace")
    from_bundle = set(RE_ASSET.findall(bundle_text))
    log(f"  assets named in the bundle: {len(from_bundle)}")

    for css in [p for p in paths if p.endswith(".css")]:
        f = root / css
        if f.is_file():
            for u in RE_CSS_URL.findall(f.read_text(encoding="utf-8", errors="replace")):
                if not u.startswith(("http", "data:")):
                    from_bundle.add(u)

    ok = failed = 0
    for i, p in enumerate(sorted(from_bundle), 1):
        if _fetch(p, root):
            ok += 1
        else:
            failed += 1
        if i % 200 == 0:
            log(f"  ... {i}/{len(from_bundle)}")

    return {"referenced": len(paths), "assets": len(from_bundle), "ok": ok, "failed": failed}


def phase_numbered(root: Path, log=_log) -> dict[str, int]:
    """Tries the numbered paths until they run out."""
    found = 0
    for folder in NUMBERED_FOLDERS:
        n = 0
        for i in range(1, MAX_NUMBER + 1):
            path = f"{folder}{i}.png"
            if (root / path).is_file() or _fetch(path, root):
                n += 1
        found += n
        log(f"  {folder}: {n}")
    return {"found": found}


def phase_slug(root: Path, log=_log) -> dict[str, int]:
    """Tries every plausible slug from the bundle in the dynamic-URL folders.

    Most attempts will 404; that is expected and harmless.
    """
    bundle = next(root.glob("js/bundle*.js"), None)
    if bundle is None:
        raise RuntimeError("bundle missing: run the static phase first")
    text = bundle.read_text(encoding="utf-8", errors="replace")

    slugs = {
        s for s in re.findall(r"""["']([a-z0-9][a-z0-9-]{2,29})["']""", text)
        if RE_SLUG.match(s) and not s.endswith(("-js", "-css"))
    }
    log(f"  candidate slugs: {len(slugs)}  x {len(SLUG_FOLDERS)} folders")

    to_try = [
        f"{c}{s}.png"
        for c in SLUG_FOLDERS
        for s in sorted(slugs)
        if not (root / f"{c}{s}.png").is_file()
    ]
    log(f"  to try: {len(to_try)} (404s are expected and normal)")

    # Low concurrency: with 24 requests in flight the site blocks us.
    found = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch, p, root): p for p in to_try}
        for i, f in enumerate(as_completed(futures), 1):
            if f.result():
                found += 1
            if i % 1000 == 0:
                log(f"  ... {i}/{len(to_try)}  ({found} found)")
    return {"tried": len(to_try), "found": found}


def phase_repair(root: Path, missing: list[str], log=_log) -> dict[str, int]:
    """Downloads exactly the files the verification reported as missing.

    The list comes from the game itself, so it is exact. Downloads are
    sequential to avoid being blocked.
    """
    ok = failed = 0
    for m in missing:
        if _fetch(m, root):
            ok += 1
        else:
            failed += 1
            log(f"  unrecoverable: {m}")
    log(f"  repaired {ok}, unrecoverable {failed}")
    return {"ok": ok, "failed": failed}


def phase_played(root: Path, runs: int = 3, port: int = 8422, log=_log) -> dict[str, int]:
    """Plays with auto-fill on, to capture the URLs built at runtime."""
    from ...core.game import Game
    from ..server import AssetServer

    server = AssetServer(root, port=port, upstream=UPSTREAM)
    server.start()
    try:
        game = Game(url=server.url)
        game.open()
        try:
            for i in range(runs):
                obs = game.reset(seed=9000 + i)
                steps = 0
                while steps < 120 and not obs.get("done") and obs.get("actions"):
                    obs = game.step(steps % len(obs["actions"]))
                    steps += 1
                log(f"  run {i + 1}/{runs}: {steps} steps, "
                    f"{len(server.fetched)} files recovered so far")
        finally:
            game.close()
    finally:
        server.stop()
    return {"recovered": len(server.fetched)}


def phase_verify(root: Path, runs: int = 2, port: int = 8423, log=_log) -> dict:
    """Replays with the network closed. Zero missing means the copy is complete."""
    from ...core.game import Game
    from ..server import AssetServer

    server = AssetServer(root, port=port, upstream=None)  # no network
    server.start()
    try:
        game = Game(url=server.url)
        game.open()
        try:
            for i in range(runs):
                obs = game.reset(seed=7000 + i)
                steps = 0
                while steps < 120 and not obs.get("done") and obs.get("actions"):
                    obs = game.step(steps % len(obs["actions"]))
                    steps += 1
                log(f"  check {i + 1}/{runs}: {steps} steps played")
            external = list(game.session.external_requests) if game.session else []
        finally:
            game.close()
    finally:
        server.stop()
    return {"missing": sorted(server.missing), "external_requests": external}
