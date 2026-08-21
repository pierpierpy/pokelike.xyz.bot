"""Finding passes on disk: listing, sorting, liveness, and selection.

In: an optional version filter. Out: pass directories, ordered by recency.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .read import Pass

from .liveness import HEARTBEAT_STALE  # noqa: F401  re-exported for the package

BENCH = Path(__file__).resolve().parents[4] / "llm-bench"

# The package re-exports BENCH and _containers, and tests monkeypatch the package
# attribute. This accessor reads from the package so patches are always visible.
_PKG = "pokelike.harness.watch"


def _bench() -> Path:
    """Return the bench path, respecting monkeypatches on the package.

    In: nothing. Out: the resolved BENCH path.
    """
    pkg = sys.modules.get(_PKG)
    return pkg.BENCH if pkg is not None else BENCH


# ----------------------------------------------------------------------- listing


def newest(version: str | None = None) -> Path | None:
    """The most recently written pass directory, over one version or all of them.

    In: optional version string. Out: a Path or None.
    """
    found = folders(version)
    return found[0] if found else None


def folders(version: str | None = None) -> list[Path]:
    """Every pass directory that has a trace, most recently written first.

    In: optional version string. Out: list of Paths sorted by recency.
    """
    bench = _bench()
    versions = [bench / version] if version else sorted(bench.glob("v*"))
    dirs = [d for v in versions for d in (v / "logs").glob("*")
            if d.is_dir() and any(d.glob("*.jsonl"))]
    return sorted(dirs, key=_touched, reverse=True)


def _touched(folder: Path) -> float:
    """Most recent mtime of any .jsonl in the folder.

    In: a directory path. Out: epoch float.
    """
    return max((f.stat().st_mtime for f in folder.glob("*.jsonl")), default=0.0)


# ----------------------------------------------------------------------- containers


def _slug(model: str) -> str:
    """A model id as `run.sh` turns it into a container name.

    In: a model string like 'qwen/qwen3.7-flash'. Out: slug like 'qwen-qwen3-7-flash'.

    `tr -c 'a-zA-Z0-9' '-' | tr -s '-'` and the ends trimmed, which is how the script
    builds `qwen-qwen3-7-flash-180247` out of `qwen/qwen3.7-flash`.
    """
    out = "".join(c if c.isalnum() else "-" for c in model)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def _has_container(model: str, names: list[str]) -> bool:
    """Is a pokelike container for this model up right now?

    In: model id and list of container names. Out: bool.

    Matched as a substring so it holds whatever named the container: run.sh's
    `qwen-qwen3-7-flash-180247` and a compose `--name pk_v4_qwen-qwen3-7-flash`
    both contain the model's slug. Only a fallback: it keeps a pass started by an
    image built before the heartbeat existed visible until it finishes.
    """
    slug = _slug(model)
    return any(slug in n for n in names)


def _containers() -> list[str]:
    """Names of the pokelike containers up right now, or nothing if docker is absent.

    In: nothing. Out: list of container name strings.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["docker", "ps", "--filter", "label=com.docker.compose.project=pokelike-llm-bench",
             "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return [n for n in out.stdout.split() if n]


def _get_containers() -> list[str]:
    """Call the package-level _containers, which may be monkeypatched by tests.

    In: nothing. Out: list of container name strings.
    """
    pkg = sys.modules.get(_PKG)
    if pkg is not None:
        return pkg._containers()
    return _containers()


# ----------------------------------------------------------------------- liveness


def live(version: str | None = None) -> list[Path]:
    """The passes that are ACTUALLY running, and nothing else.

    In: optional version string. Out: list of live pass directory Paths.

    A pass is running when it is still refreshing its heartbeat (the one signal
    that survives every way a run can stop), or, as a fallback for a pass from an
    image older than the heartbeat, when a container is up for it. A pass whose
    log already says `done` or `FAILED` is finished, never running, however
    recently it wrote.

    There is deliberately no "written in the last N minutes" window: that showed a
    killed pass as alive for minutes and a slow one as dead. If it is not proven
    running, it is not here.
    """
    from .read import read

    up = _get_containers()
    return [d for d in folders(version)
            if (p := read(d, up)) is not None and p.state == "running"]


# ----------------------------------------------------------------------- selection


def _started(folder: Path) -> tuple[int, str]:
    """When the pass was launched, for ordering a list of them.

    In: a pass directory. Out: a (priority, iso-timestamp) tuple for sorting.

    From `command.json`, whose `at` carries a UTC offset, so a pass started in a
    container (UTC) and one started on the host (UTC+2) sort against each other
    correctly. The directory name cannot do that: it is local time in both cases and
    the two clocks are two hours apart. Falls back to the name when there is no
    command file, which is only ever a half-written directory.
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
    """Which pass to follow, from what was asked for and what is running.

    In: optional version, stamp, and model filters. Out: a Path or None.

    Asked rather than guessed when more than one is live. Following whichever was
    written to last is not merely arbitrary with two passes going: the last write
    alternates between them, so the view would flip every couple of seconds and
    neither pass would be readable.
    """
    from rich.console import Console
    from rich.prompt import IntPrompt

    from .read import read

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
        # Nothing running means nothing to watch. NOT the most recent pass on disk:
        # a finished run offered as "live" is exactly the confusion this removes.
        return running[0] if running else None

    # Numbered by when each pass STARTED, because a number has to mean the same thing
    # twice in a row. Ordered by last write, which is how everything else here is
    # ordered, the list reshuffled between two invocations: the 3 you chose a minute
    # ago was the 1 you chose now, and both were the same pass.
    running.sort(key=_started)
    up = _get_containers()

    console = Console()
    if not console.is_terminal:
        # Nobody to ask. The one being written to is as good an answer as any, and
        # saying which it settled on is what stops the number being read as another.
        chosen = max(running, key=_touched)
        console.print(f"[dim]{len(running)} passes going, following "
                      f"{chosen.name}[/dim]")
        return chosen

    console.print(f"{len(running)} passes are going, oldest first:\n")
    for i, d in enumerate(running, 1):
        p = read(d, up)
        where = f"{p.done}/{p.wanted or '?'} runs" if p else "?"
        # The state belongs in the list. A pass whose container is gone still reads
        # as a candidate for a few minutes, and picking it to find out is worse than
        # being told here.
        mark = "" if p is None or p.state == "running" else f"  [yellow]{p.state}[/yellow]"
        console.print(f"  [bold]{i}[/bold]  {d.parent.parent.name}  "
                      f"{p.model if p else '?':<34} {where:<12}"
                      f"[dim]{d.name}[/dim]{mark}")
    console.print()
    n = IntPrompt.ask("which one", choices=[str(i) for i in range(1, len(running) + 1)],
                      default="1", show_default=True)
    return running[int(n) - 1]
