"""This module starts and stops a game so that a caller does not have to assemble
the pieces manually. All public names from the sub-modules are re-exported here.

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
