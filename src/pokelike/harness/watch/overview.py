"""The overview tables for `pokelike model watch --all` and `pokelike model watch -o`.

The overview() function shows every pass on disk, one row each, newest first. The
monitor() function shows only the running passes with live progress bars, refreshed
in place.
"""

from __future__ import annotations

import time

from ...shared.tokens import tok as _tok
from .discover import (
    BENCH,
    _get_containers,
    _started,
    _touched,
    folders,
    live,
)
from .read import read


def overview(version: str | None = None) -> int:
    """Shows every pass on disk, one row each, newest first."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    folders_found = folders(version)
    if not folders_found:
        console.print("[dim]no pass has been played on this machine yet[/dim]")
        return 1

    up = _get_containers()
    t = Table(border_style="dim", header_style="bold")
    t.add_column("started")
    t.add_column("v")
    t.add_column("model", no_wrap=True, min_width=26)
    t.add_column("runs", justify="right")
    t.add_column("badges~", justify="right")
    t.add_column("state")
    t.add_column("last", justify="right")
    for d in folders_found:
        p = read(d, up)
        if p is None:
            continue
        finished = p.runs[: p.done] if p.state == "running" else p.runs
        mean = (sum(r.badges for r in finished) / len(finished)) if finished else 0.0
        tone = {"running": "green", "done": "cyan", "stalled": "yellow",
                "stopped": "blue", "FAILED": "red"}.get(p.state, "white")
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


def _running_table(version: str | None):
    """Returns one row per running pass, with a progress bar and summary stats.

    The return value is (table, n) where n is the number of running passes.
    """
    from rich.table import Table

    from ..llmbench.pricing import cached_prices, cost

    # Estimated cost at today's list price, fetched once and cached. A model
    # that the list does not know prints a dash instead.
    price = cached_prices()

    up = _get_containers()
    running = sorted(live(version), key=_started)
    t = Table(border_style="dim", header_style="bold")
    t.add_column("#", justify="right")
    t.add_column("v")
    t.add_column("model", no_wrap=True, min_width=26)
    t.add_column("progress", no_wrap=True)
    t.add_column("badges~", justify="right")
    t.add_column("tok in/out", justify="right")
    t.add_column("cost", justify="right")
    t.add_column("fell", justify="right")
    t.add_column("eta", justify="right")
    t.add_column("stamp", justify="right")
    for i, d in enumerate(running, 1):
        p = read(d, up)
        if p is None:
            continue
        total = p.wanted or 50
        done = p.done
        width = 18
        filled = int(round(width * done / total)) if total else 0
        bar = (f"[green]{'█' * filled}[/green][dim]{'░' * (width - filled)}[/dim]"
               f" {done:>2}/{total}")
        finished = p.runs[:done]
        mean = sum(r.badges for r in finished) / len(finished) if finished else 0.0
        tin = sum(r.tokens_in for r in finished)
        tout = sum(r.tokens_out for r in finished)
        fell = sum(r.fell for r in finished)
        # This is the dollar value of tokens consumed so far.
        spent = cost(tin, tout, price.get(p.model))
        money = f"${spent:.2f}" if spent is not None else "[dim]-[/dim]"
        left = "[dim]-[/dim]"
        if done and total > done:
            per = sum(r.secs for r in finished) / done
            rest = (total - done) * per
            left = f"{rest / 3600:.1f}h" if rest > 5400 else f"{rest / 60:.0f}m"
        t.add_row(str(i), p.version, p.model, bar, f"{mean:.2f}",
                  f"{_tok(tin)}/{_tok(tout)}", money,
                  f"[yellow]{fell}[/yellow]" if fell else "0",
                  left, f"[dim]{d.name}[/dim]")
    return t, len(running)


def monitor(version: str | None = None, every: float = 2.0) -> int:
    """Shows all running passes at once, refreshed in place (`model watch -o`).

    Only running passes appear; a finished or killed pass drops off when its
    heartbeat stops. The function exits on its own when nothing is left running.
    """
    from rich.console import Console
    from rich.live import Live

    console = Console()
    table, n = _running_table(version)
    if n == 0:
        console.print("nothing is running right now.")
        console.print("everything on disk:  uv run pokelike model watch --all")
        return 1
    # When piped or not a terminal, the snapshot is drawn once.
    if not console.is_terminal:
        console.print(table)
        return 0

    with Live(table, console=console, refresh_per_second=4, screen=False) as view:
        while True:
            time.sleep(every)
            table, n = _running_table(version)
            view.update(table)
            if n == 0:
                break
    console.print("all passes finished.")
    return 0
