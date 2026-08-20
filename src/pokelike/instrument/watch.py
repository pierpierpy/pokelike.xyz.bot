"""Watching a pass while it plays: `pokelike model watch`.

WHY THIS READS THE TRACE AND NOTHING ELSE. A pass writes four files and this reads
three of them, all of which are already on disk for other reasons. Nothing here talks
to the running process, so it works the same on a container, on a pass started in
another terminal, and on one that finished last week. It also cannot slow a run down
or, worse, change what the model was asked.

`<model>-passN.jsonl` is the source for everything except two things. One decision per
line, so the last line is where the model is right now, and grouping by seed gives the
finished runs without parsing the columns of the human log. The two exceptions are
whether the pass ended, which is a word in the `.log`, and the notes a harness before
v4 was holding, which only the notebook file records.

WHAT IT DOES NOT DO. No history, no aggregate across passes, no cost. `pokelike model
board` answers those, over recorded results, which is a different question from what is
happening in the next two minutes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

BENCH = Path(__file__).resolve().parents[3] / "llm-bench"


# ----------------------------------------------------------------------- reading


@dataclass
class Run:
    """One seed, finished or in flight."""

    seed: int
    steps: int = 0
    badges: int = 0
    map: int = 0
    fell: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    first_at: str = ""
    last_at: str = ""
    screen: str = ""
    why: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)

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
    plan: str = ""

    @property
    def done(self) -> int:
        # The last run is the one being played, unless the pass is over.
        return max(len(self.runs) - (1 if self.state == "running" else 0), 0)

    @property
    def current(self) -> Run | None:
        return self.runs[-1] if self.runs and self.state == "running" else None


def newest(version: str | None = None) -> Path | None:
    """The most recently written pass directory, over one version or all of them."""
    versions = [BENCH / version] if version else sorted(BENCH.glob("v*"))
    dirs = [d for v in versions for d in (v / "logs").glob("*") if d.is_dir()]
    traced = [d for d in dirs if any(d.glob("*.jsonl"))]
    return max(traced, key=lambda d: max(f.stat().st_mtime for f in d.glob("*.jsonl")),
               default=None)


def read(folder: Path) -> Pass | None:
    """Everything the dashboard shows, from the files in one pass directory."""
    trace = max(folder.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, default=None)
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
        r.why = e.get("why") or ""
        r.tools = e.get("tools") or []
        if str(e.get("why") or "").startswith("(fell back"):
            r.fell += 1

    # Whether it is still going is a word in the human log, and nowhere else: a
    # trace that stops looks the same whether the pass finished or the container
    # was killed.
    log = trace.with_suffix(".log")
    if log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
        if "\nFAILED" in text or text.startswith("FAILED"):
            p.state = "FAILED"
        elif "\ndone " in text:
            p.state = "done"
        elif trace.stat().st_mtime < time.time() - 300:
            # Neither finished nor failed, and nothing written for five minutes.
            # Saying "running" about a container that is gone is how you wait for
            # something that will never arrive.
            p.state = "stalled"

    # Never fewer than have been played. `--seeds` takes a range as two numbers in
    # some older command files, and a pass that says it wanted 2 and played 50 reads
    # as a bug in the pass rather than in the file it was read from.
    p.wanted = max(p.wanted, len(p.runs))

    p.notes = _notes(folder, trace)
    p.plan = _plan(folder, trace)
    return p


def _notes(folder: Path, trace: Path) -> list[str]:
    """The notes as of the last finished run, from the notebook file.

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
            block.append(line.strip())
    return block


def _plan(folder: Path, trace: Path) -> str:
    f = folder / f"{trace.stem}-plan.log"
    if not f.is_file():
        return ""
    last = ""
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("  ") and line.strip():
            last = line.strip()
    return last


# ---------------------------------------------------------------------- drawing


def _fmt_tokens(n: int) -> str:
    return f"{n / 1000:.0f}k" if n else "0"


def _panel(p: Pass, containers: list[str]):
    from rich.panel import Panel
    from rich.table import Table

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("harness", f"{p.version}   [dim]{p.model}[/dim]")
    left = ""
    if p.done and p.wanted and p.state == "running":
        # From the trace's own clock, so a pass written before `at` existed has no
        # per-run time and gets no estimate rather than one that reads "0 min".
        per = sum(r.secs for r in p.runs[:-1]) / p.done
        rest = (p.wanted - p.done) * per
        if rest > 5400:
            left = f"   about {rest / 3600:.1f}h left"
        elif rest:
            left = f"   about {rest / 60:.0f} min left"
    grid.add_row("progress", f"{p.done}/{p.wanted or '?'} runs{left}")
    tone = {"running": "green", "done": "cyan", "stalled": "yellow",
            "FAILED": "red"}.get(p.state, "white")
    grid.add_row("state", f"[{tone}]{p.state}[/{tone}]"
                 + (f"   [dim]{', '.join(containers)}[/dim]" if containers else ""))
    if p.notes_max:
        grid.add_row("notes cap", str(p.notes_max))
    grid.add_row("trace", f"[dim]{p.trace}[/dim]")
    return Panel(grid, title="pass", title_align="left", border_style="dim")


def _runs_table(p: Pass, limit: int = 12):
    from rich.table import Table

    t = Table(expand=False, border_style="dim", header_style="bold")
    for name in ("seed", "badges", "steps", "in", "out", "fell", "secs"):
        t.add_column(name, justify="right")
    finished = p.runs[: p.done] if p.state == "running" else p.runs
    for r in finished[-limit:]:
        t.add_row(str(r.seed), str(r.badges), str(r.steps),
                  _fmt_tokens(r.tokens_in), _fmt_tokens(r.tokens_out),
                  f"[yellow]{r.fell}[/yellow]" if r.fell else "0",
                  f"{r.secs:.0f}" if r.secs else "[dim]-[/dim]")
    if not finished:
        t.add_row(*["[dim]-[/dim]"] * 7)
    return t


def _turn(p: Pass):
    """What the model is doing right now: where it is, what it chose, what it used."""
    from rich.panel import Panel
    from rich.table import Table

    r = p.current
    if r is None:
        return Panel("[dim]no run in flight[/dim]", title="this turn",
                     title_align="left", border_style="dim")
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("seed", f"{r.seed}   step {r.steps}   {r.screen}")
    grid.add_row("badges", f"{r.badges}   map {r.map}")
    grid.add_row("said", (r.why or "[dim](nothing)[/dim]")[:160])
    if r.tools:
        lines = []
        for c in r.tools:
            bits = [f"[bold]{c.get('tool')}[/bold]"]
            for k, v in c.items():
                if k == "tool":
                    continue
                bits.append(f"[dim]{k}[/dim] {str(v)[:90]}")
            lines.append("  ".join(bits))
        grid.add_row("tools", "\n".join(lines))
    return Panel(grid, title="this turn", title_align="left", border_style="dim")


def _memory(p: Pass):
    from rich.panel import Panel

    body = "\n".join(p.notes) if p.notes else "[dim]nothing written yet[/dim]"
    if p.plan:
        body += f"\n\n[bold]plan[/bold]  {p.plan}"
    return Panel(body, title="memory", title_align="left", border_style="dim")


def _containers() -> list[str]:
    """Names of the pokelike containers up right now, or nothing if docker is absent."""
    import subprocess

    try:
        out = subprocess.run(
            ["docker", "ps", "--filter", "label=com.docker.compose.project=pokelike-llm-bench",
             "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return [n for n in out.stdout.split() if n]


def render(p: Pass, containers: list[str]):
    from rich.console import Group

    return Group(_panel(p, containers), _runs_table(p), _turn(p), _memory(p))


def overview(version: str | None = None) -> int:
    """Every pass on disk, one row each, newest first.

    The other half of the question. The live view answers "what is it doing", this
    answers "what is on this machine and which of it is still moving", which is what
    you want after an hour away and before you kill anything.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    versions = [BENCH / version] if version else sorted(BENCH.glob("v*"))
    folders = sorted(
        (d for v in versions for d in (v / "logs").glob("*")
         if d.is_dir() and any(d.glob("*.jsonl"))),
        key=lambda d: max(f.stat().st_mtime for f in d.glob("*.jsonl")), reverse=True)
    if not folders:
        console.print("[dim]no pass has been played on this machine yet[/dim]")
        return 1

    up = _containers()
    t = Table(border_style="dim", header_style="bold")
    t.add_column("started")
    t.add_column("v")
    t.add_column("model", no_wrap=True, min_width=26)
    t.add_column("runs", justify="right")
    t.add_column("badges~", justify="right")
    t.add_column("state")
    t.add_column("last", justify="right")
    for d in folders:
        p = read(d)
        if p is None:
            continue
        finished = p.runs[: p.done] if p.state == "running" else p.runs
        mean = (sum(r.badges for r in finished) / len(finished)) if finished else 0.0
        tone = {"running": "green", "done": "cyan", "stalled": "yellow",
                "FAILED": "red"}.get(p.state, "white")
        age = time.time() - max(f.stat().st_mtime for f in d.glob("*.jsonl"))
        t.add_row(d.name, p.version, p.model,
                  f"{p.done}/{p.wanted or '?'}", f"{mean:.2f}",
                  f"[{tone}]{p.state}[/{tone}]",
                  f"{age / 60:.0f} min" if age < 5400 else f"{age / 3600:.0f} h")
    console.print(t)
    if up:
        console.print(f"  up now: {', '.join(up)}")
    recorded = sorted(f.name for f in BENCH.glob("v*/results/*.json"))
    console.print(f"  recorded: {len(recorded)} "
                  f"[dim]{'  '.join(recorded[:4])}{'  ...' if len(recorded) > 4 else ''}[/dim]")
    return 0


def dashboard(version: str | None = None, once: bool = False,
              every: float = 2.0) -> int:
    """The pass that was written to last, redrawn until it ends or you stop it."""
    from rich.console import Console
    from rich.live import Live

    console = Console()
    folder = newest(version)
    if folder is None:
        where = f"llm-bench/{version}/logs" if version else "llm-bench/*/logs"
        console.print(f"nothing to watch: no trace under {where}")
        console.print("start one with:  bash llm-bench/run.sh <model> --harness <v>")
        return 1

    p = read(folder)
    if p is None:
        console.print(f"{folder} holds no trace yet")
        return 1
    # Redrawing in place needs a terminal to redraw in. Piped to a file or a pager it
    # would write nothing at all, so it draws once and stops, which is what the pipe
    # was asking for anyway.
    if once or not console.is_terminal:
        console.print(render(p, _containers()))
        return 0

    with Live(render(p, _containers()), console=console, refresh_per_second=4,
              screen=False) as live:
        while True:
            time.sleep(every)
            # The newest directory again, not the one we started on: a sweep moves
            # to the next model in a new directory, and following the pass you asked
            # about beats following the one that happened to be first.
            folder = newest(version) or folder
            fresh = read(folder)
            if fresh is None:
                continue
            p = fresh
            live.update(render(p, _containers()))
            if p.state in ("done", "FAILED"):
                break
    return 0
