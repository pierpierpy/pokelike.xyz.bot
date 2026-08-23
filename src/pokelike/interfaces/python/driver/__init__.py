"""Starting and stopping a game, so a caller does not have to assemble it.

Re-exports all public names from the sub-modules.

Two shapes:

    with session() as game:      a script. Closed on the way out, exceptions too.
    game = open_game()           a notebook. Stays alive across cells.
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
