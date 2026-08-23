"""Harness versions, paths, fingerprints, and the slug that names a result file."""

from __future__ import annotations

import hashlib
from pathlib import Path

# --------------------------------------------------------------------------- paths

from ...shared.paths import BENCH, ROOT  # noqa: F401 (re-exported for callers)

# These shared (not frozen) files are fingerprinted so that changes are reported.
BROWSER = Path(__file__).resolve().parent.parent.parent / "core" / "browser.py"
GAME = Path(__file__).resolve().parent.parent.parent / "core" / "game.py"
RUNNER = Path(__file__).resolve().parent.parent.parent / "core" / "runner.py"


def _bench() -> Path:
    """Returns the BENCH path through sys.modules so monkeypatching in tests propagates."""
    import sys
    pkg = sys.modules.get(__package__)
    if pkg is not None and hasattr(pkg, "BENCH"):
        return pkg.BENCH
    return BENCH


def versions() -> list[str]:
    """Returns the harness versions on disk, oldest first."""
    bench = _bench()
    if not bench.is_dir():
        return []
    found = [d.name for d in bench.iterdir()
             if d.is_dir() and (d / "harness" / "bot.py").is_file()]
    return sorted(found, key=lambda v: int(v.lstrip("v") or 0))


def harness_path(version: str) -> Path:
    p = _bench() / version / "harness" / "bot.py"
    if not p.is_file():
        have = ", ".join(versions()) or "none"
        raise FileNotFoundError(f"no harness at {p} (versions on disk: {have})")
    return p


def render_path(version: str) -> Path:
    """Returns the renderer frozen beside this harness.

    Every harness must carry its own renderer because a harness without one
    would measure against the shared module, which the CLI is free to improve
    at any time.
    """
    p = _bench() / version / "harness" / "render.py"
    if not p.is_file():
        raise FileNotFoundError(
            f"no renderer at {p}. Every harness carries its own: copy the one "
            f"from the previous version rather than importing pokelike.core.render."
        )
    return p


def script_paths(version: str) -> dict[str, Path]:
    """Returns the two JavaScript files (bridge.js, init.js) this harness uses.

    These files decide what the state is. The bridge.js file chooses which fields
    exist and the action order, and init.js pins Math.random and Date.now (the
    run seed). Both are frozen per version and handed to `Game(bridge=..., init=...)`.
    """
    bench = _bench()
    out = {}
    for key, name in (("bridge", "bridge.js"), ("init", "init.js")):
        p = bench / version / "harness" / name
        if not p.is_file():
            raise FileNotFoundError(
                f"no {name} at {p}. Every harness carries its own copy: take the "
                f"one from the previous version, or from src/pokelike/core/ if this "
                f"is a new idea rather than a re-run of an old one."
            )
        out[key] = p
    return out


def slug(model: str) -> str:
    """Converts a model id into a safe filename. `openai/gpt-4o-mini` -> `openai--gpt-4o-mini`."""
    return model.replace("/", "--").replace(":", "-").replace(" ", "-")


def fingerprints(version: str) -> dict[str, str]:
    """Returns SHA-256 hashes (truncated to 16 hex) of the seven files the measurement depends on.

    The seven files are four frozen files beside the harness (bot.py, render.py,
    bridge.js, init.js) and three shared files (browser.py, game.py, runner.py)
    that drive the game. The game bundle is recorded separately as `game` because
    the bundle is downloaded rather than committed. This fingerprint is provenance
    ("which bytes played this") and does not indicate whether a change could have
    moved a score. See the `behaviour` function below for that check.
    """
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]  # noqa: E731
    frozen = {"bot.py": harness_path(version), "render.py": render_path(version)}
    frozen.update({f"{k}.js": v for k, v in script_paths(version).items()})
    shared = {f"shared/{p.name}": p for p in (BROWSER, GAME, RUNNER)}
    return {k: sha(v) for k, v in {**frozen, **shared}.items()}


# In-process only, keyed on the seven-key fingerprint, so a version whose files
# have not changed since the last call in this process never replays twice.
# The cache is not persisted, so a fresh process always verifies rather than
# trusting a claim written by an earlier, possibly stale, run of this same code.
_BEHAVIOUR_CACHE: dict[tuple[str, ...], str] = {}


def behaviour(version: str, site) -> str:
    """Returns this version's behaviour hash, which indicates whether the engine still decides the same thing.

    This function plays a short deterministic replay (see `pokelike.shared.fingerprint`)
    through this version's own bridge.js and init.js, using the shared browser.py,
    game.py, and runner.py exactly as a real pass would. Two versions whose seven
    files hash differently (a comment, a rename) but decide every replay identically
    return the same behaviour hash. A version that changed what any decision resolves
    to, however small, returns a different hash. The `site` parameter is the asset
    server root already on disk (see `assets.server.AssetServer`). This function does
    not download the site.
    """
    from ...shared.fingerprint import behaviour_hash_for

    key = tuple(sorted(fingerprints(version).values()))
    cached = _BEHAVIOUR_CACHE.get(key)
    if cached is not None:
        return cached
    result = behaviour_hash_for(site, **script_paths(version))
    _BEHAVIOUR_CACHE[key] = result
    return result


def cross_run_memory(version: str) -> bool:
    """Returns whether this harness lets the model carry notes from one run into the next.

    The check inspects the harness class for a `CROSS_RUN_MEMORY` attribute.
    """
    from ...bot.catalogue import load_class

    return bool(getattr(load_class(harness_path(version)), "CROSS_RUN_MEMORY", False))
