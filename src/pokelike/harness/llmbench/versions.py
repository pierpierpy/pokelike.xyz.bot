"""Harness versions, paths, fingerprints, and the slug that names a result file.

Every model benchmark needs to know which version it is running under, where the
frozen files live, and what content was on disk when the pass began. This module
answers all three, and nothing else.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# --------------------------------------------------------------------------- paths
#
# __file__ is now one directory deeper than it was when this lived at
# src/pokelike/harness/llmbench.py, so the parent count goes up by one.
# Before: Path(__file__).resolve().parents[3] pointed at the repo root.
# Now:    Path(__file__).resolve().parents[4] does.

ROOT = Path(__file__).resolve().parents[4]
BENCH = ROOT / "llm-bench"

# Shared and NOT frozen: what drives the game, as opposed to what decides what the
# game shows. Fingerprinted so a change is reported rather than absorbed.
BROWSER = Path(__file__).resolve().parent.parent.parent / "core" / "browser.py"
GAME = Path(__file__).resolve().parent.parent.parent / "core" / "game.py"
RUNNER = Path(__file__).resolve().parent.parent.parent / "core" / "runner.py"


def _bench() -> Path:
    """Access BENCH through the package so monkeypatching L.BENCH propagates.

    Tests patch `L.BENCH` (the __init__ attribute). Functions here must see that
    patched value, so they go through `sys.modules[__package__]` rather than
    reading the module-level name directly. The module-level BENCH is still
    exported for normal (non-patched) code that reads the attribute.
    """
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
    """The renderer frozen beside this harness.

    Required, not optional. A harness that rendered with the shared module would
    be measuring against a file the CLI is free to improve, which is the whole
    thing this directory exists to avoid; and letting the key vanish when the
    file is missing would turn a hole into silence, since a key nobody recorded
    is a key nobody checks.
    """
    p = _bench() / version / "harness" / "render.py"
    if not p.is_file():
        raise FileNotFoundError(
            f"no renderer at {p}. Every harness carries its own: copy the one "
            f"from the previous version rather than importing pokelike.core.render."
        )
    return p


def script_paths(version: str) -> dict[str, Path]:
    """The two JavaScript files this harness drives the game with.

    Frozen for a stronger reason than the renderer. A renderer decides how the
    state is shown; these decide what the state IS. `bridge.js` chooses which
    fields exist and the order `actions` come in, and a bot answers with an INDEX
    into that list, so reordering silently changes what the same answer means.
    `init.js` replaces Math.random and Date.now, and the run seed is built from
    both: move a constant there and every seed maps to a different run, which does
    not mark a recorded score, it voids it.

    Handed to `Game(bridge=..., init=...)`, so the choice lives in the harness
    directory rather than in the code that runs it.
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
    """What the measurement actually depended on.

    Four files frozen beside the harness, and three shared ones hashed because
    they cannot be.

    The frozen four are everything that decides what a run IS: the loop, the text
    the model reads, the state it is built from, and the pins that make a seed
    replay. None of them can move under a recorded row, because nothing outside
    that directory touches them.

    The shared three drive the game. They are hashed rather than copied because
    copying them would mean a harness carrying its own browser plumbing, which is
    640 lines to freeze an engineering detail; when they change it is normally for
    reasons that are not about content, and the mark is there to say so.

    Not hashed: the game bundle, which is recorded separately as `game` because it
    is downloaded rather than committed and has its own name and sha.

    History. This used to be two keys, the harness and `pokelike.core.render`, on
    the argument that copying the renderer would be worse than fingerprinting it.
    That failed on the first real case: a defect in the shared renderer could not
    be fixed for the person at the terminal without marking every score ever
    recorded, so the benchmark was holding the CLI hostage. See ARCHITECTURE.md.
    """
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]  # noqa: E731
    frozen = {"bot.py": harness_path(version), "render.py": render_path(version)}
    frozen.update({f"{k}.js": v for k, v in script_paths(version).items()})
    shared = {f"shared/{p.name}": p for p in (BROWSER, GAME, RUNNER)}
    return {k: sha(v) for k, v in {**frozen, **shared}.items()}


def cross_run_memory(version: str) -> bool:
    """Whether this harness lets the model carry notes from one run into the next.

    Asked of the harness rather than hardcoded here, because the harness is the
    thing that knows: v1 declares `CROSS_RUN_MEMORY = True`, and a future version
    that drops the idea says so by not declaring it. Nothing in this file has to
    be edited when a version is added.

    Reading it means importing the harness module, which is cheap and needs no
    credentials: the class is only inspected, never constructed.
    """
    from ...bot.catalogue import load_class

    return bool(getattr(load_class(harness_path(version)), "CROSS_RUN_MEMORY", False))
