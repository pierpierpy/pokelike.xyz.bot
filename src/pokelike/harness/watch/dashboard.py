"""The interactive per-pass follow view for `pokelike model watch`.

This module draws the dashboard for a single pass and redraws it in place until the
pass ends or the user stops it. The five panels (pass info, runs table, this turn,
team+map, memory) are each a pure function of the Pass record read from disk.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ...shared.tokens import tok as _tok

if TYPE_CHECKING:
    from .read import Pass


# ---------------------------------------------------------------------- drawing


def _panel(p: "Pass", containers: list[str]):
    from rich.panel import Panel
    from rich.table import Table

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("harness", f"{p.version}   [dim]{p.model}[/dim]")
    left = ""
    if p.done and p.wanted and p.state == "running":
        # From the trace's own clock. A pass without per-run timestamps gets no
        # estimate rather than an estimate that reads "0 min".
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
    if p.settings_text:
        grid.add_row("set", f"[cyan]{p.settings_text}[/cyan]")
    if p.notes_max:
        grid.add_row("notes cap", str(p.notes_max))
    grid.add_row("trace", f"[dim]{p.trace}[/dim]")
    return Panel(grid, title="pass", title_align="left", border_style="dim")


def _runs_table(p: "Pass", limit: int = 12):
    from rich.table import Table

    t = Table(expand=False, border_style="dim", header_style="bold")
    for name in ("seed", "badges", "score", "steps", "in", "out", "fallback", "secs"):
        t.add_column(name, justify="right")
    finished = p.runs[: p.done] if p.state == "running" else p.runs
    for r in finished[-limit:]:
        t.add_row(str(r.seed), str(r.badges),
                  "[dim]-[/dim]" if r.score is None else str(r.score),
                  str(r.steps),
                  _tok(r.tokens_in), _tok(r.tokens_out),
                  ("0" if not r.fell
                   else f"[yellow]{r.fell_share * 100:.1f}%[/yellow]"
                   if r.fell_share > 0.1 else f"{r.fell_share * 100:.1f}%"),
                  f"{r.secs:.0f}" if r.secs else "[dim]-[/dim]")
    if not finished:
        t.add_row(*["[dim]-[/dim]"] * 8)
    return t


def _turn(p: "Pass"):
    """Renders the current decision, showing where the model is, what it chose, and what it used."""
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
    # The region is shown beside the map because the map number restarts at every boundary.
    where = f"   region {r.region}" if r.region else ""
    grid.add_row("badges", f"{r.badges}   map {r.map}{where}")
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


def _team_and_map(p: "Pass"):
    """Renders the team at the last decision beside the map, shown side by side."""
    from rich.columns import Columns
    from rich.panel import Panel

    r = p.current or (p.runs[-1] if p.runs else None)
    # A run at the character-select screen has no team and no map yet, which
    # differs from a trace that never carries team or map data at all.
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


def _memory(p: "Pass"):
    from rich.panel import Panel

    notes = p.notes_live or p.notes
    # Notes are numbered as the model sees them, because those numbers are what
    # the model passes to `revise` and `forget`.
    body = ("\n".join(f"[{i}] {n}" for i, n in enumerate(notes, 1)) if notes
            else "[dim]nothing written yet[/dim]")
    if p.plan:
        body += f"\n\n[bold]plan[/bold]  {p.plan}"
    title = "memory"
    if p.notes_live != p.notes:
        # The notebook file is per finished run, so notes_live and notes differ
        # exactly when the current run has touched the notebook.
        title = "memory, this turn"
    return Panel(body, title=title, title_align="left", border_style="dim")


_BLOCKS = " ▁▂▃▄▅▆▇█"


def _spark(values: list[float], lo: float, hi: float) -> str:
    """Draws one bar per value, scaled between lo and hi.

    The scale is passed in rather than taken from the data so that two rows drawn
    one under the other can be read against each other, and so a flat run of
    identical values does not stretch to fill the height.
    """
    if hi <= lo:
        return _BLOCKS[1] * len(values)
    out = []
    for v in values:
        frac = (v - lo) / (hi - lo)
        idx = min(len(_BLOCKS) - 1, max(1, int(round(frac * (len(_BLOCKS) - 1)))))
        out.append(_BLOCKS[idx])
    return "".join(out)


def _progress(p: "Pass"):
    """Returns a panel showing whether the model is getting better as the pass goes.

    Two rows over the same horizontal axis, one bar per finished run in play
    order. The first row is the badges of each run, which is noisy because seeds
    differ in difficulty. The second is the mean of every run up to that point,
    which is the line to read for a trend, since it only moves when a run pulls
    the average with it.

    Each row carries its own vertical range, printed beside it. A shared range
    would flatten the mean into a straight line, because the mean of thirty runs
    moves within a few tenths of a badge while single runs swing by whole badges,
    and a flat line would read as no trend rather than as the wrong scale.

    The panel is left out entirely before six runs, because the two halves of the
    comparison would share runs and the number would say nothing.
    """
    from rich.panel import Panel
    from rich.table import Table

    curve = p.badge_curve
    if len(curve) < 6:
        return None
    running = [sum(curve[: i + 1]) / (i + 1) for i in range(len(curve))]
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column(no_wrap=True)
    grid.add_column(style="dim", no_wrap=True)

    b_hi = max(curve) or 1
    grid.add_row("badges/run",
                 f"[dim]{_spark([float(c) for c in curve], 0, float(b_hi))}[/dim]",
                 f"0 to {b_hi}")
    m_lo, m_hi = min(running), max(running)
    grid.add_row("mean so far", _spark(running, m_lo, m_hi),
                 f"{m_lo:.2f} to {m_hi:.2f}, now {running[-1]:.2f}")
    delta = p.learn
    if delta is not None:
        k = min(10, len(curve) // 2)
        first = sum(curve[:k]) / k
        last = sum(curve[-k:]) / k
        tone = "green" if delta > 0 else "red" if delta < 0 else "white"
        grid.add_row("learn",
                     f"first {k} runs {first:.2f}   last {k} runs {last:.2f}   "
                     f"[{tone}]{delta:+.2f}[/{tone}]", "")
    return Panel(grid, title="is it improving", title_align="left",
                 border_style="dim")


def render(p: "Pass", containers: list[str]):
    from rich.console import Group

    # The chart is absent for the first few runs, so the parts are filtered rather
    # than leaving a hole in the layout.
    parts = [_panel(p, containers), _runs_table(p), _progress(p), _turn(p),
             _team_and_map(p), _memory(p)]
    return Group(*[x for x in parts if x is not None])


def dashboard(version: str | None = None, once: bool = False,
              every: float = 2.0, stamp: str | None = None,
              model: str | None = None) -> int:
    """Redraws the chosen pass until it ends or the user stops it."""
    from rich.console import Console
    from rich.live import Live

    from .discover import _get_containers, folders, pick
    from .read import read

    console = Console()
    folder = pick(version, stamp=stamp, model=model)
    if folder is None:
        if stamp or model:
            console.print(f"no pass here matches {stamp or model}")
            console.print("what there is:  uv run pokelike model watch --all")
            return 1
        if folders(version):
            # Traces exist but none is running.
            console.print("nothing is running right now.")
            console.print("everything on disk:  uv run pokelike model watch --all")
            return 1
        where = f"llm-bench/{version}/logs" if version else "llm-bench/*/logs"
        console.print(f"nothing to watch: no trace under {where}")
        console.print("start one with:  pokelike model bench --harness <v> "
                      "--model <id> --docker")
        return 1

    p = read(folder, _get_containers())
    if p is None:
        console.print(f"{folder} holds no trace yet")
        return 1
    # When piped or not a terminal, the dashboard is drawn once and stops.
    if once or not console.is_terminal:
        console.print(render(p, _get_containers()))
        return 0

    with Live(render(p, _get_containers()), console=console, refresh_per_second=4,
              screen=False) as live_view:
        while True:
            time.sleep(every)
            # The same directory is always re-read, rather than whichever was
            # written to last. With two passes going the view would otherwise
            # flip between them.
            fresh = read(folder, _get_containers())
            if fresh is None:
                continue
            p = fresh
            live_view.update(render(p, _get_containers()))
            if p.state in ("done", "FAILED", "stalled"):
                # The pass finished or died, so there is nothing more to redraw.
                break
    return 0
