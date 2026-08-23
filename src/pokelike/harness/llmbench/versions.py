"""Harness versions, paths, fingerprints, and the slug that names a result file."""

from __future__ import annotations

import hashlib
from pathlib import Path

# --------------------------------------------------------------------------- paths

ROOT = Path(__file__).resolve().parents[4]
BENCH = ROOT / "llm-bench"

# Shared (not frozen) files fingerprinted so changes are reported.
BROWSER = Path(__file__).resolve().parent.parent.parent / "core" / "browser.py"
GAME = Path(__file__).resolve().parent.parent.parent / "core" / "game.py"
RUNNER = Path(__file__).resolve().parent.parent.parent / "core" / "runner.py"


def _bench() -> Path:
    """Returns BENCH through sys.modules so monkeypatching in tests propagates."""
    import sys
    pkg = sys.modules.get(__package__)
    if pkg is not None and hasattr(pkg, "BENCH"):
        return pkg.BENCH
    return BENCH


def versions() -> list[str]:
    """Harness versions on disk, oldest first."""
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
    """The renderer frozen beside this harness. Required, not optional.

    A harness without its own renderer would measure against the shared module,
    which the CLI is free to improve at any time.
    """
    p = _bench() / version / "harness" / "render.py"
    if not p.is_file():
        raise FileNotFoundError(
            f"no renderer at {p}. Every harness carries its own: copy the one "
            f"from the previous version rather than importing pokelike.core.render."
        )
    return p


def script_paths(version: str) -> dict[str, Path]:
    """The two JavaScript files (bridge.js, init.js) this harness uses.

    These decide what the state IS: bridge.js chooses which fields exist and the
    action order, and init.js pins Math.random and Date.now (the run seed). Both
    are frozen per version. Handed to `Game(bridge=..., init=...)`.
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
    """A model id as a filename. `openai/gpt-4o-mini` -> `openai--gpt-4o-mini`."""
    return model.replace("/", "--").replace(":", "-").replace(" ", "-")


def fingerprints(version: str) -> dict[str, str]:
    """SHA-256 hashes (truncated to 16 hex) of the seven files the measurement depends on.

    Four frozen files beside the harness (bot.py, render.py, bridge.js, init.js)
    and three shared files (browser.py, game.py, runner.py) that drive the game.
    The game bundle is recorded separately as `game` because it is downloaded, not
    committed.
    """
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]  # noqa: E731
    frozen = {"bot.py": harness_path(version), "render.py": render_path(version)}
    frozen.update({f"{k}.js": v for k, v in script_paths(version).items()})
    shared = {f"shared/{p.name}": p for p in (BROWSER, GAME, RUNNER)}
    return {k: sha(v) for k, v in {**frozen, **shared}.items()}


def cross_run_memory(version: str) -> bool:
    """Whether this harness lets the model carry notes from one run into the next.

    Determined by inspecting the harness class for a `CROSS_RUN_MEMORY` attribute.
    """
    from ...bot.catalogue import load_class

    return bool(getattr(load_class(harness_path(version)), "CROSS_RUN_MEMORY", False))
