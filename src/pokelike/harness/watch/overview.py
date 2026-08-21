"""The overview tables: `pokelike model watch --all` and `pokelike model watch -o`.

Two views that answer "what is on this machine":
  overview()  -- every pass on disk, one row each, newest first
  monitor()   -- only the running passes, with live progress bars, refreshed in place
"""

from __future__ import annotations

import time

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


def _running_table(version: str | None):
    """The `pick` list, live: one row per running pass, plus a bar and some stats.

    Same shape you choose from (number, version, model, runs, stamp), with a
    tqdm-style progress bar and the numbers worth glancing at while it runs:
    mean badges so far, tokens in/out, fallbacks, and a rough ETA. Returns
    (table, n).
    """
    from rich.table import Table

    from ..llmbench.pricing import cached_prices, cost

    def toks(n: int) -> str:
        return f"{n / 1e6:.1f}M" if n >= 1e6 else (f"{n / 1e3:.0f}k" if n else "0")

    # What the tokens already counted would cost at today's list price, fetched once
    # and cached because this table redraws every couple of seconds. A model the
    # list does not know (a self-hosted endpoint, say) prints a dash: not free,
    # unknown. Money is never stored in a result, only derived here, so a price
    # change cannot rewrite what a pass measured.
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
        # Cents, not dollars: a flash model twenty runs in is often under a dollar,
        # and "$0" would read as free rather than as cheap.
        spent = cost(tin, tout, price.get(p.model))
        money = f"${spent:.2f}" if spent is not None else "[dim]-[/dim]"
        left = "[dim]-[/dim]"
        if done and total > done:
            per = sum(r.secs for r in finished) / done
            rest = (total - done) * per
            left = f"{rest / 3600:.1f}h" if rest > 5400 else f"{rest / 60:.0f}m"
        t.add_row(str(i), p.version, p.model, bar, f"{mean:.2f}",
                  f"{toks(tin)}/{toks(tout)}", money,
                  f"[yellow]{fell}[/yellow]" if fell else "0",
                  left, f"[dim]{d.name}[/dim]")
    return t, len(running)


def monitor(version: str | None = None, every: float = 2.0) -> int:
    """Every RUNNING pass at once, each with a live progress bar (`model watch -o`).

    The list from `pick()`, but drawn in place and refreshed, and never asking which
    to follow: it follows all of them. Only running passes appear, so a finished or
    killed one drops off the list the moment its heartbeat stops. Exits on its own
    when nothing is left running.
    """
    from rich.console import Console
    from rich.live import Live

    console = Console()
    table, n = _running_table(version)
    if n == 0:
        console.print("nothing is running right now.")
        console.print("everything on disk:  uv run pokelike model watch --all")
        return 1
    # Piped or no terminal: draw the snapshot once, do not spin.
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
