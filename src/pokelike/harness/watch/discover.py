"""Finding passes on disk, including listing, sorting, liveness checks, and selection."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .read import Pass

from .liveness import HEARTBEAT_STALE  # noqa: F401  re-exported for the package

from ...shared.paths import BENCH  # noqa: F401  re-exported for the package

# The package re-exports BENCH and _containers, and tests monkeypatch the package
# attribute. This accessor reads from the package so patches are always visible.
_PKG = "pokelike.harness.watch"


def _bench() -> Path:
    """Returns the bench path, respecting monkeypatches on the package."""
    pkg = sys.modules.get(_PKG)
    return pkg.BENCH if pkg is not None else BENCH


# ----------------------------------------------------------------------- listing


def newest(version: str | None = None) -> Path | None:
    """Returns the most recently written pass directory, over one version or all of them."""
    found = folders(version)
    return found[0] if found else None


def folders(version: str | None = None) -> list[Path]:
    """Returns every pass directory that has a trace, most recently written first."""
    bench = _bench()
    # This import is local to avoid a circular import between the two modules.
    from .read import RUNS_SUFFIX

    versions = [bench / version] if version else sorted(bench.glob("v*"))
    dirs = [d for v in versions for d in (v / "logs").glob("*")
            if d.is_dir() and any(f for f in d.glob("*.jsonl")
                                  if not f.name.endswith(RUNS_SUFFIX))]
    return sorted(dirs, key=_touched, reverse=True)


def _touched(folder: Path) -> float:
    """Returns the most recent mtime of any .jsonl in the folder."""
    return max((f.stat().st_mtime for f in folder.glob("*.jsonl")), default=0.0)


# ----------------------------------------------------------------------- containers


def _slug(model: str) -> str:
    """Converts a model id to the slug a container name carries.

    This replaces non-alphanumeric characters with hyphens and collapses runs of
    hyphens, e.g. 'qwen/qwen3.7-flash' becomes 'qwen-qwen3-7-flash'.
    """
    out = "".join(c if c.isalnum() else "-" for c in model)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def _has_container(model: str, names: list[str]) -> bool:
    """Returns True when a running pokelike container's name contains this model's slug.

    The slug is matched as a substring so both `qwen-qwen3-7-flash-180247` and a
    compose name like `pk_v4_qwen-qwen3-7-flash` match.
    """
    slug = _slug(model)
    return any(slug in n for n in names)


def _containers() -> list[str]:
    """Returns names of running pokelike containers, or an empty list if docker is absent."""
    import subprocess

    try:
        out = subprocess.run(
            ["docker", "ps", "--filter", "label=com.docker.compose.project=pokelike-llm-bench",
             # The heartbeat records the container id as hostname, so both
             # names and ids must be matchable.
             "--format", "{{.Names}} {{.ID}}"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return [n for n in out.stdout.split() if n]


def _get_containers() -> list[str]:
    """Calls the package-level _containers, which may be monkeypatched by tests."""
    pkg = sys.modules.get(_PKG)
    if pkg is not None:
        return pkg._containers()
    return _containers()


# ----------------------------------------------------------------------- liveness


def live(version: str | None = None) -> list[Path]:
    """Returns passes that are actively running right now.

    A pass is running when its heartbeat file is fresh, or (as a fallback for
    passes from before the heartbeat existed) when a container is up for the model.
    A pass whose log already says `done` or `FAILED` is never included.
    """
    from .read import RUNS_SUFFIX, read

    up = _get_containers()
    return [d for d in folders(version)
            if (p := read(d, up)) is not None and p.state == "running"]


# ----------------------------------------------------------------------- selection


def _started(folder: Path) -> tuple[int, str]:
    """Returns the sort key for ordering passes by launch time.

    This reads the `at` field from `command.json` (which carries a UTC offset for
    correct cross-timezone ordering). The function falls back to the directory name
    when no command file exists.
    """
    f = folder / "command.json"
    if f.is_file():
        try:
            at = json.loads(f.read_text(encoding="utf-8")).get("at")
            if at:
                return (0, datetime.fromisoformat(at).astimezone().isoformat())
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return (1, folder.name)


def pick(version: str | None = None, stamp: str | None = None,
         model: str | None = None) -> "Path | None":
    """Selects which pass to follow, from the given filters and what is running.

    When more than one pass is live, this prompts interactively. In non-interactive
    mode, the most recently written pass is chosen.
    """
    from rich.console import Console
    from rich.prompt import IntPrompt

    from .read import RUNS_SUFFIX, read

    if stamp or model:
        for d in folders(version):
            if stamp and stamp not in d.name:
                continue
            if model and model.replace("/", "--") not in " ".join(
                    f.name for f in d.glob("*.jsonl")):
                continue
            return d
        return None

    running = live(version)
    if len(running) < 2:
        # Returns a live pass, or None if none is running. A finished pass
        # on disk is not offered here.
        return running[0] if running else None

    # The list is sorted by start time so the numbering stays stable between invocations.
    running.sort(key=_started)
    up = _get_containers()

    console = Console()
    if not console.is_terminal:
        # There is no terminal to prompt in, so the most recently written pass is chosen.
        chosen = max(running, key=_touched)
        console.print(f"[dim]{len(running)} passes going, following "
                      f"{chosen.name}[/dim]")
        return chosen

    console.print(f"{len(running)} passes are going, oldest first:\n")
    for i, d in enumerate(running, 1):
        p = read(d, up)
        where = f"{p.done}/{p.wanted or '?'} runs" if p else "?"
        # The state is shown so a stalled pass is visible without selecting it.
        mark = "" if p is None or p.state == "running" else f"  [yellow]{p.state}[/yellow]"
        console.print(f"  [bold]{i}[/bold]  {d.parent.parent.name}  "
                      f"{p.model if p else '?':<34} {where:<12}"
                      f"[dim]{d.name}[/dim]{mark}")
    console.print()
    n = IntPrompt.ask("which one", choices=[str(i) for i in range(1, len(running) + 1)],
                      default="1", show_default=True)
    return running[int(n) - 1]
