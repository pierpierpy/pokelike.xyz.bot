"""Parsing a pass's trace into Run and Pass records.

In: the path to a pass directory. Out: a Pass record with its runs and totals.

In-process, from the files on disk. No conversation with the running process, so it
works on a container, on a pass started in another terminal, and on one that finished
last week. It also cannot slow a run down or, worse, change what the model was asked.

`<model>-passN.jsonl` is the source for everything except two things. One decision per
line, so the last line is where the model is right now, and grouping by seed gives the
finished runs without parsing the columns of the human log. The two exceptions are
whether the pass ended, which is a word in the `.log`, and the notes a harness before
v4 was holding, which only the notebook file records.
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

from .liveness import _alive_fresh

# What a pass calls the file of finished runs, written beside the trace. Named
# here because two things need it: skipping it when looking for the trace, and
# finding it when looking for the scores.
RUNS_SUFFIX = "-runs.jsonl"


# ----------------------------------------------------------------------- data


@dataclass
class Run:
    """One seed, finished or in flight."""

    seed: int
    steps: int = 0
    badges: int = 0
    # The engine's own points_no_time, known only once the run is over, so it
    # arrives from the pass's runs file rather than from the decision trace. None
    # while the run is in flight, and on passes older than that file.
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


def newest_trace(folder: Path) -> Path | None:
    """The pass's decision trace, which is not the only .jsonl beside it.

    In: a pass directory. Out: the trace path, or None when there is none.
    """
    # A pass also writes `<pass>-runs.jsonl`, one line per FINISHED run, and that
    # file is written last, so picking "the newest .jsonl" would eventually pick it
    # and read the wrong file as the trace. The suffix is excluded here, in one
    # place, rather than at each of the four sites that look for a trace.
    traces = [f for f in folder.glob("*.jsonl") if not f.name.endswith(RUNS_SUFFIX)]
    return max(traces, key=lambda f: f.stat().st_mtime, default=None)


def read(folder: Path, up: list[str] | None = None) -> Pass | None:
    """Everything the dashboard shows, from the files in one pass directory.

    In: a pass directory path, optional container name list. Out: a Pass or None.

    `up` is the current container list; pass it and a pass with no heartbeat but a
    live container still reads as running (the pre-heartbeat fallback). Omit it and
    liveness rests on the heartbeat alone.
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

    # `openai--gpt-4o-mini-pass1.jsonl` back to a model id. The command file names
    # every model of the sweep, so it cannot say which one this file is.
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
            # The last line can be half written. Nothing to fix, it arrives whole
            # a moment later.
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
        # Carried forward: the enrichment only writes it on a non-Kanto turn, and a
        # turn without it is not a turn that went back to Kanto.
        r.region = e.get("region") or r.region
        r.why = e.get("why") or ""
        r.tools = e.get("tools") or []
        # Kept for the whole run, not just the last turn: the notes as they stand now
        # are the last finished notebook with this run's operations applied.
        r.ops.extend(c for c in (e.get("tools") or [])
                     if c.get("tool") in ("remember", "revise", "forget"))
        r.team = e.get("team") or r.team
        # Written only when it changed, so the last one seen is the current one. Kept
        # per run, because a run that ends leaves its own last map behind it.
        r.map_view = e.get("map_view") or r.map_view
        if str(e.get("why") or "").startswith("(fell back"):
            r.fell += 1

    # Whether it is still going is a word in the human log, and nowhere else: a
    # trace that stops looks the same whether the pass finished or the container
    # was killed. Failing that, the clock.
    log = trace.with_suffix(".log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    if "\nFAILED" in text or text.startswith("FAILED"):
        p.state = "FAILED"
    elif "\nSTOPPED" in text or text.startswith("STOPPED"):
        # Ended on purpose (`model stop`, `docker stop`, Ctrl-C). Its own word, so
        # it is not read as a failure and not read as a finished pass either: the
        # seeds it did not play were never played.
        p.state = "stopped"
    elif "\ndone " in text:
        p.state = "done"
    elif _alive_fresh(trace) and not _owner_gone(trace, up):
        # The pass is still touching its heartbeat: running. The heartbeat is the
        # signal, and it stops the instant the process does, however it stopped.
        #
        # The one addition is not a guess: a pass WRITES who is playing it into that
        # file, so when it names a container that is no longer up, the pass is over
        # now rather than in five minutes' time. That matters after `model stop`,
        # where the container's own files are root-owned and the heartbeat cannot be
        # removed from outside, so without this the pass would sit in `model watch`
        # looking alive until the mtime aged out.
        p.state = "running"
    else:
        # Not finished, and not touching its heartbeat: it stopped and nothing said
        # so (a kill, an OOM, a power cut, a removed container). Not running.
        p.state = "stalled"

    # Never fewer than have been played. `--seeds` takes a range as two numbers in
    # some older command files, and a pass that says it wanted 2 and played 50 reads
    # as a bug in the pass rather than in the file it was read from.
    _add_scores(trace, p)
    p.wanted = max(p.wanted, len(p.runs))

    p.notes = _notes(folder, trace)
    p.plan = _plan(folder, trace)
    p.notes_live = _replay(p)
    return p


def _replay(p: Pass) -> list[str]:
    """The notes as they stand THIS turn, not as they stood when a run last ended.

    In: a Pass record. Out: the list of live notes with mid-run ops applied.

    The notebook file is written per finished run, so a note written five turns ago sat
    in a dashboard that said "nothing written yet" until the run ended. Under v4 every
    operation is in the trace with the text, so the current state is the last finished
    notebook with this run's operations applied on top.

    Refused operations are skipped, which is the whole reason `refused` is recorded: a
    `remember` against a full notebook changed nothing and must not read as if it did.

    A harness that does not record its operations gets the per-run notebook and nothing
    else, which is all there is to have.
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
    """The notes as of the last finished run, from the notebook file.

    In: pass directory and trace path. Out: list of note strings.

    Read from the file rather than rebuilt from the trace, because a harness before
    v4 does not record what it did to its notes, only what it was holding when a run
    ended. What v4 did THIS run is in the current turn instead.
    """
    f = folder / f"{trace.stem}-notebook.log"
    if not f.is_file():
        return []
    block: list[str] = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("run "):
            if "unchanged" not in line:
                block = []
        elif line.startswith("  ["):
            # The file writes `  [1] a note`. The number is stripped here and put
            # back by whoever draws it, so a replayed operation and a note read
            # from the file are numbered by the same thing.
            _, _, text = line.strip().partition("] ")
            block.append(text or line.strip())
    return block


def _plan(folder: Path, trace: Path) -> str:
    """The last plan line from the plan log file.

    In: pass directory and trace path. Out: the plan string (empty if none).
    """
    f = folder / f"{trace.stem}-plan.log"
    if not f.is_file():
        return ""
    last = ""
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("  ") and line.strip():
            last = line.strip()
    return last


def _add_scores(trace: Path, p: "Pass") -> None:
    """Fills in each finished run's score from the pass's runs file.

    In: the trace path (the runs file sits beside it) and the Pass to complete.
    Out: nothing, the runs are updated in place.
    """
    # A pass writes one JSON line per finished run, which is the only place the
    # score exists while the pass is still playing: the decision trace is per
    # decision, and a score is not known until the run ends. Absent for passes
    # started before this file existed, and the score simply stays None there.
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


def _owner_gone(trace: Path, up: list[str] | None) -> bool:
    """Whether the pass's own process is provably no longer there.

    In: the trace path (the heartbeat sits beside it) and the containers up now.
    Out: True only when the pass said who was playing it and that is demonstrably
    gone.
    """
    # Conservative by construction, because a false True hides a pass that is
    # genuinely playing, which is exactly what it did on the first attempt: a pass
    # running OUTSIDE a container writes this machine's hostname, that can never
    # appear in a list of container names, and so every local pass looked dead the
    # moment any container happened to be up.
    #
    # So the two cases are told apart rather than lumped together:
    #   this machine  -> the pid is in OUR namespace and can be asked directly
    #   anything else -> a container id, which is gone when it is not up
    # Anything unknown (no owner line, an older pass, no docker) leaves the
    # heartbeat as the only signal, exactly as before.
    alive = trace.with_suffix(".alive")
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
        # A pid that no longer exists is the fastest honest answer there is. One
        # that does is trusted, and it does not matter that pids are eventually
        # reused: a reused pid means a live process, and the heartbeat it is being
        # judged with was fresh anyway.
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    # A container id. Only decidable when there is a list to compare against.
    if not up:
        return False
    return not any(host == x or x.startswith(host) or host.startswith(x) for x in up)
