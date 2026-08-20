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


def newest(version: str | None = None) -> Path | None:
    """The most recently written pass directory, over one version or all of them."""
    found = folders(version)
    return found[0] if found else None


def folders(version: str | None = None) -> list[Path]:
    """Every pass directory that has a trace, most recently written first."""
    versions = [BENCH / version] if version else sorted(BENCH.glob("v*"))
    dirs = [d for v in versions for d in (v / "logs").glob("*")
            if d.is_dir() and any(d.glob("*.jsonl"))]
    return sorted(dirs, key=_touched, reverse=True)


def _touched(folder: Path) -> float:
    return max((f.stat().st_mtime for f in folder.glob("*.jsonl")), default=0.0)


def _slug(model: str) -> str:
    """A model id as `run.sh` turns it into a container name.

    `tr -c 'a-zA-Z0-9' '-' | tr -s '-'` and the ends trimmed, which is how the script
    builds `qwen-qwen3-7-flash-180247` out of `qwen/qwen3.7-flash`.
    """
    out = "".join(c if c.isalnum() else "-" for c in model)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def live(version: str | None = None, within: float = 900.0) -> list[Path]:
    """The passes that are actually going.

    ASKED OF DOCKER FIRST, because docker is the only thing that knows. Deciding this
    from the clock alone was wrong in both directions: a pass killed a minute ago still
    looked alive, and a pass whose turn was taking six minutes looked dead. With three
    containers up you should be offered three passes, and that is what a container list
    says without any guessing.

    `run.sh` names each container after the model it plays, so the match is by model. If
    two passes of one model are on disk and one container is up for it, the one still
    being written to is the one that container is writing.

    Nothing running under docker at all, or no docker: the clock is the fallback, with a
    minute's window, which is what a pass being played on the host looks like.

    A pass that has said `done` or `FAILED` in its log is never live however recently it
    wrote. That was a finished dry run offered as a choice, three seconds old, at the top
    of the list because it had written last.
    """
    up = {n.rsplit("-", 1)[0] for n in _containers()}
    now = time.time()
    out: list[Path] = []
    claimed: set[str] = set()
    for d in folders(version):
        age = now - _touched(d)
        if age >= within:
            continue
        p = read(d)
        if p is None or p.state in ("done", "FAILED"):
            continue
        slug = _slug(p.model)
        if slug in up:
            # One container, one pass. Folders come newest first, so the first match
            # is the one that container is writing to.
            if slug in claimed:
                continue
            claimed.add(slug)
        elif not (up and age > 60):
            # No container for this model. Either nothing is containerised at all, in
            # which case the clock decides, or this pass is being played on the host
            # right now and is writing as we look.
            pass
        else:
            continue
        out.append(d)
    return out


def _started(folder: Path) -> tuple[int, str]:
    """When the pass was launched, for ordering a list of them.

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
         model: str | None = None) -> Path | None:
    """Which pass to follow, from what was asked for and what is running.

    Asked rather than guessed when more than one is live. Following whichever was
    written to last is not merely arbitrary with two passes going: the last write
    alternates between them, so the view would flip every couple of seconds and
    neither pass would be readable.
    """
    from rich.console import Console
    from rich.prompt import IntPrompt

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
        return running[0] if running else newest(version)

    # Numbered by when each pass STARTED, because a number has to mean the same thing
    # twice in a row. Ordered by last write, which is how everything else here is
    # ordered, the list reshuffled between two invocations: the 3 you chose a minute
    # ago was the 1 you chose now, and both were the same pass.
    running.sort(key=_started)

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
        p = read(d)
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
    elif "\ndone " in text:
        p.state = "done"
    elif _touched(folder) < time.time() - 300:
        # Neither finished nor failed, and nothing written for five minutes. Saying
        # "running" about a container that is gone is how you wait for something that
        # will never arrive.
        p.state = "stalled"

    # Never fewer than have been played. `--seeds` takes a range as two numbers in
    # some older command files, and a pass that says it wanted 2 and played 50 reads
    # as a bug in the pass rather than in the file it was read from.
    p.wanted = max(p.wanted, len(p.runs))

    p.notes = _notes(folder, trace)
    p.plan = _plan(folder, trace)
    p.notes_live = _replay(p)
    return p


def _replay(p: Pass) -> list[str]:
    """The notes as they stand THIS turn, not as they stood when a run last ended.

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


def _team_and_map(p: Pass):
    """The team as it stood at the last decision, beside the map it is standing on.

    Side by side because they are one question. A team at half health matters because
    of what is on the next layer, and a gym two layers down matters because of what
    the team can take into it.
    """
    from rich.columns import Columns
    from rich.panel import Panel

    r = p.current or (p.runs[-1] if p.runs else None)
    # A run at the character select has no team and no map yet, which is not the
    # same as a trace that never carries them. Saying the wrong one of those sends
    # you looking for a bug in the logger.
    ever_team = any(x.team for x in p.runs)
    ever_map = any(x.map_view for x in p.runs)
    nothing_team = "[dim]not yet[/dim]" if ever_team else "[dim]not in this trace[/dim]"
    nothing_map = "[dim]not yet[/dim]" if ever_map else "[dim]not in this trace[/dim]"
    team = "\n".join(r.team) if r and r.team else nothing_team
    picture = r.map_view if r and r.map_view else nothing_map
    return Columns([
        Panel(team, title="team", title_align="left", border_style="dim"),
        Panel(picture, title=f"map {r.map if r else '?'}", title_align="left",
              border_style="dim"),
    ])


def _memory(p: Pass):
    from rich.panel import Panel

    notes = p.notes_live or p.notes
    # Numbered as the model sees them, because the numbers are what it passes to
    # `revise` and `forget` and what the trace records.
    body = ("\n".join(f"[{i}] {n}" for i, n in enumerate(notes, 1)) if notes
            else "[dim]nothing written yet[/dim]")
    if p.plan:
        body += f"\n\n[bold]plan[/bold]  {p.plan}"
    title = "memory"
    if p.notes_live != p.notes:
        # Says which it is showing. The file behind `notes` is per finished run, so
        # the two differ exactly when this run has touched them.
        title = "memory, this turn"
    return Panel(body, title=title, title_align="left", border_style="dim")


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

    return Group(_panel(p, containers), _runs_table(p), _turn(p),
                 _team_and_map(p), _memory(p))


def overview(version: str | None = None) -> int:
    """Every pass on disk, one row each, newest first.

    The other half of the question. The live view answers "what is it doing", this
    answers "what is on this machine and which of it is still moving", which is what
    you want after an hour away and before you kill anything.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    folders_found = folders(version)
    if not folders_found:
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
    for d in folders_found:
        p = read(d)
        if p is None:
            continue
        finished = p.runs[: p.done] if p.state == "running" else p.runs
        mean = (sum(r.badges for r in finished) / len(finished)) if finished else 0.0
        tone = {"running": "green", "done": "cyan", "stalled": "yellow",
                "FAILED": "red"}.get(p.state, "white")
        age = time.time() - _touched(d)
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
              every: float = 2.0, stamp: str | None = None,
              model: str | None = None) -> int:
    """The pass you chose, redrawn until it ends or you stop it."""
    from rich.console import Console
    from rich.live import Live

    console = Console()
    folder = pick(version, stamp=stamp, model=model)
    if folder is None:
        if stamp or model:
            console.print(f"no pass here matches {stamp or model}")
            console.print("what there is:  uv run pokelike model watch --all")
            return 1
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
              screen=False) as live_view:
        while True:
            time.sleep(every)
            # THE SAME directory, not whichever was written to last. With two passes
            # going the last write alternates between them, and the view would flip
            # every couple of seconds with neither one readable.
            fresh = read(folder)
            if fresh is None:
                continue
            p = fresh
            live_view.update(render(p, _containers()))
            if p.state in ("done", "FAILED"):
                break
    return 0
