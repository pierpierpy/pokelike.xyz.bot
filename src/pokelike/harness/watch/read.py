"""Parsing a pass's trace into Run and Pass records.

This module reads the files on disk without contacting the running process. The
decision trace (`<model>-passN.jsonl`) is the primary source, with one line per
decision grouped by seed for finished runs. The `.log` supplies whether the pass
ended, and the notebook file supplies notes for harnesses before v4.
"""

from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .liveness import _alive_fresh, heartbeat

# The runs file uses this suffix and is written beside the trace.
RUNS_SUFFIX = "-runs.jsonl"


# ----------------------------------------------------------------------- data


@dataclass
class Run:
    """Represents one seed's run, whether finished or still in flight."""

    seed: int
    steps: int = 0
    badges: int = 0
    # The engine's points_no_time, known only once the run ends. The value is None while in flight.
    score: int | None = None
    map: int = 0
    fell: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    first_at: str = ""
    last_at: str = ""
    screen: str = ""
    region: str = ""
    why: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)
    ops: list[dict[str, Any]] = field(default_factory=list)
    team: list[str] = field(default_factory=list)
    map_view: str = ""

    @property
    def secs(self) -> float:
        try:
            a = datetime.fromisoformat(self.first_at)
            b = datetime.fromisoformat(self.last_at)
        except (TypeError, ValueError):
            return 0.0
        return (b - a).total_seconds()


@dataclass
class Pass:
    """A pass as the files on disk describe it."""

    folder: Path
    version: str
    model: str
    trace: Path
    wanted: int = 0
    workers: int = 1
    notes_max: int = 0
    started: str = ""
    state: str = "running"
    runs: list[Run] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    notes_live: list[str] = field(default_factory=list)
    plan: str = ""

    @property
    def done(self) -> int:
        # The last run is the one being played, unless the pass is over.
        return max(len(self.runs) - (1 if self.state == "running" else 0), 0)

    @property
    def current(self) -> Run | None:
        return self.runs[-1] if self.runs and self.state == "running" else None


# ----------------------------------------------------------------------- reading


def _companions(files: list[Path]) -> set[Path]:
    """Returns the files that belong to another file in the list rather than standing alone.

    Every file a pass writes is its trace's stem plus a suffix, so
    `<stem>-chat.jsonl` and `<stem>-runs.jsonl` sit beside `<stem>.jsonl`. A file
    is therefore a companion when its name starts with another file's stem
    followed by a dash. Reading the relationship off the names keeps this
    correct when a pass starts writing a new kind of file, which a list of known
    suffixes would not.
    """
    return {f for f in files
            if any(f.name.startswith(g.stem + "-") for g in files if g != f)}


def newest_trace(folder: Path) -> Path | None:
    """Returns the trace of the most recently active pass in the folder.

    The companion files are excluded before the comparison because they are
    written more often than the trace itself. The conversations file is appended
    on every model call, so comparing modification times across all of them
    would pick it and every path derived from it, the heartbeat included, would
    name a file that does not exist.
    """
    files = list(folder.glob("*.jsonl"))
    traces = [f for f in files if f not in _companions(files)]
    return max(traces, key=lambda f: f.stat().st_mtime, default=None)


def read(folder: Path, up: list[str] | None = None) -> Pass | None:
    """Build a Pass record from the files in one pass directory.

    The `up` list contains the current container names. Passing the list allows a
    pass with no heartbeat but a live container to still read as running (a
    pre-heartbeat fallback).
    """
    trace = newest_trace(folder)
    if trace is None:
        return None
    cmd = {}
    if (folder / "command.json").is_file():
        try:
            cmd = json.loads((folder / "command.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cmd = {}

    # The model id is extracted from the trace filename.
    stem = trace.stem.rsplit("-pass", 1)[0]
    p = Pass(
        folder=folder,
        version=folder.parent.parent.name,
        model=stem.replace("--", "/"),
        trace=trace,
        wanted=int(cmd.get("runs") or 0) or len(cmd.get("seeds") or []),
        workers=int(cmd.get("workers") or 1),
        notes_max=int(cmd.get("notes") or 0),
        started=cmd.get("at", ""),
    )

    by_seed: dict[int, Run] = {}
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            # The last line can be half written; skip it.
            continue
        seed = e.get("seed")
        if seed is None:
            continue
        r = by_seed.get(seed)
        if r is None:
            r = by_seed[seed] = Run(seed=seed, first_at=e.get("at", ""))
            p.runs.append(r)
        r.steps = max(r.steps, int(e.get("step") or 0) + 1)
        r.badges = int(e.get("badges") or 0)
        r.map = int(e.get("map") or 0)
        r.tokens_in = int(e.get("run_in") or 0)
        r.tokens_out = int(e.get("run_out") or 0)
        r.last_at = e.get("at", "") or r.last_at
        r.screen = e.get("screen") or ""
        # The region is carried forward because absence does not mean Kanto.
        r.region = e.get("region") or r.region
        r.why = e.get("why") or ""
        r.tools = e.get("tools") or []
        # Notebook operations are accumulated for the whole run.
        r.ops.extend(c for c in (e.get("tools") or [])
                     if c.get("tool") in ("remember", "revise", "forget"))
        r.team = e.get("team") or r.team
        # The map_view is written only when it changed, so keep the last seen per run.
        r.map_view = e.get("map_view") or r.map_view
        if str(e.get("why") or "").startswith("(fell back"):
            r.fell += 1

    # Terminal state comes from the human log because a trace that simply stops
    # gives no indication whether the pass finished or was killed.
    log = trace.with_suffix(".log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    if "\nFAILED" in text or text.startswith("FAILED"):
        p.state = "FAILED"
    elif "\nSTOPPED" in text or text.startswith("STOPPED"):
        # The pass ended on purpose (`model stop`, `docker stop`, or Ctrl-C).
        p.state = "stopped"
    elif "\ndone " in text:
        p.state = "done"
    elif _alive_fresh(folder) and not _owner_gone(folder, up):
        # The heartbeat is fresh and the owner process is not provably gone.
        p.state = "running"
    else:
        # There is no terminal state in the log and no fresh heartbeat, so the pass is stalled.
        p.state = "stalled"

    # The wanted count must never be less than what was actually played.
    _add_scores(trace, p)
    p.wanted = max(p.wanted, len(p.runs))

    p.notes = _notes(folder, trace)
    p.plan = _plan(folder, trace)
    p.notes_live = _replay(p)
    return p


def _replay(p: Pass) -> list[str]:
    """Returns the notes as they stand this turn, with mid-run ops applied on top.

    The notebook file is written per finished run, so this method applies the
    current run's operations on top of the last persisted notebook. Refused
    operations are skipped. A harness that does not record operations gets only
    the per-run notebook.
    """
    r = p.current
    if r is None:
        return list(p.notes)
    notes = list(p.notes)
    for c in r.ops:
        if c.get("refused"):
            continue
        op, note, i = c.get("tool"), c.get("note"), c.get("id")
        if op == "remember" and note:
            notes.append(str(note))
        elif op == "forget" and isinstance(i, int) and 1 <= i <= len(notes):
            notes.pop(i - 1)
        elif op == "revise" and note and isinstance(i, int) and 1 <= i <= len(notes):
            notes[i - 1] = str(note)
    return notes


def _notes(folder: Path, trace: Path) -> list[str]:
    """Returns the notes as of the last finished run, read from the notebook file."""
    f = folder / f"{trace.stem}-notebook.log"
    if not f.is_file():
        return []
    block: list[str] = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("run "):
            if "unchanged" not in line:
                block = []
        elif line.startswith("  ["):
            # The `[1]` prefix is stripped here; numbering is applied at display time.
            _, _, text = line.strip().partition("] ")
            block.append(text or line.strip())
    return block


def _plan(folder: Path, trace: Path) -> str:
    """Returns the last plan line from the plan log file."""
    f = folder / f"{trace.stem}-plan.log"
    if not f.is_file():
        return ""
    last = ""
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("  ") and line.strip():
            last = line.strip()
    return last


def _add_scores(trace: Path, p: "Pass") -> None:
    """Fill in each finished run's score from the pass's runs file."""
    # The runs file holds one JSON line per finished run, including the score.
    path = trace.with_name(trace.stem + RUNS_SUFFIX)
    if not path.is_file():
        return
    by_seed = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue          # the last line can be half written
            if row.get("seed") is not None:
                by_seed[int(row["seed"])] = row.get("score")
    except OSError:
        return
    for r in p.runs:
        if r.seed in by_seed:
            r.score = by_seed[r.seed]


def _owner_gone(folder: Path, up: list[str] | None) -> bool:
    """Returns True when the pass's owner process is provably no longer there.

    The function returns True only when the heartbeat file names an owner
    (hostname/pid or container id) that is demonstrably gone. It returns False
    for anything unknown.
    """
    # Locally the pid is checked directly; for a container the id is compared
    # against the list of running containers. Anything unknown leaves the
    # heartbeat as the only signal.
    alive = heartbeat(folder)
    if alive is None:
        return False
    try:
        text = alive.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    owner = dict(re.findall(r"(pid|host)=(\S+)", text))
    host = owner.get("host")
    if not host:
        return False

    if host == socket.gethostname():
        pid = owner.get("pid", "")
        if not pid.isdigit():
            return False
        # A dead pid means the process is gone.
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    # For a container id, the check is only possible when there is a list to compare against.
    if not up:
        return False
    return not any(host == x or x.startswith(host) or host.startswith(x) for x in up)
