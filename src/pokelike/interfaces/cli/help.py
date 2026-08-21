"""Help text: the three boxed command families and the epilog builder."""

from __future__ import annotations

import argparse

# rich when installed, plain argparse when not. The help has to render in an
# environment where an optional dependency failed to install.
try:
    from rich_argparse import RawDescriptionRichHelpFormatter as _FORMATTER
except ImportError:  # pragma: no cover
    _FORMATTER = argparse.RawDescriptionHelpFormatter


# Three boxes, one per thing this repo does, and every command lives in exactly one.
FAMILIES = (
    ("the game", (
        ("setup", "browser plus an offline copy of the game. Once"),
        ("play", "play it yourself in the terminal"),
        ("api", "drive it over HTTP"),
        ("schema", "what a bot receives: state, actions, node kinds"),
        ("history", "what you have played here"),
        ("mirror", "rebuild the offline copy if it breaks"))),
    ("pokelike bot", (
        ("new", "write a bot folder that already plays"),
        ("run", "play it and watch the decisions"),
        ("bench", "the 50 standard seeds, records a result"),
        ("board", "the standings"))),
    ("pokelike model", (
        ("bench", "a model against one frozen harness version"),
        ("board", "what has been measured, per version"),
        ("watch", "follow a pass while it plays"),
        ("stop", "end a running pass, keeping everything it wrote"))),
)

_FAMILY = dict(FAMILIES)   # name -> verbs, for the per-group boxes


def _boxes(families) -> str:
    """One bordered box per family (title + its verbs). Shared by the top-level
    help and by every group screen, so all of them look the same.

    Falls back to plain text rather than failing: `--help` is the one thing that
    must work even where an optional dependency did not install.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:  # pragma: no cover
        out = [""]
        for name, verbs in families:
            out.append(f"{name}:")
            out += [f"  {v:<9}{h}" for v, h in verbs]
            out.append("")
        return "\n".join(out)

    console = Console(width=min(84, Console().width), record=True)
    with console.capture() as cap:
        console.print()
        for name, verbs in families:
            verb_rows = Table.grid(padding=(0, 2))
            verb_rows.add_column(style="bold",
                                 width=max(len(v) for v, _ in verbs) + 1)
            verb_rows.add_column()
            for verb, help_ in verbs:
                verb_rows.add_row(verb, help_)
            console.print(Panel(
                verb_rows,
                title=f"[bold]{name}[/bold]",
                title_align="left", border_style="dim", padding=(0, 1),
            ))
            console.print()
    return cap.get()


def groups_epilog() -> str:
    return _boxes(FAMILIES)
