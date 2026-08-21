"""Starting and stopping a game, so a caller does not have to assemble it.

In: nothing at the package level. Out: re-exports of all public names.

Everything was importable and nothing was ready to use: playing one run meant
finding the offline copy, starting an asset server, choosing a port that is free,
opening a browser, and closing both afterwards. Five lines of identical
boilerplate at the top of every script anyone wrote against this repo.

Two shapes, because they are genuinely different situations:

    with session() as game:      a script. Closed on the way out, exceptions too.
    game = open_game()           a notebook. `with` does not span cells, so the
                                 game has to outlive the one that opened it.
"""

from .compare import compare, format_comparison
from .play import evaluate, play
from .session import (
    SITE,
    HostedGame,
    ThreadedGame,
    free_port,
    open_game,
    session,
)

__all__ = [
    "session", "open_game", "play", "evaluate", "compare", "format_comparison",
    "free_port", "HostedGame", "ThreadedGame", "SITE",
]
