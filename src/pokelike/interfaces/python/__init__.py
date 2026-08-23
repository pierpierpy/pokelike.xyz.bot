"""This module drives the game from Python, the third interface beside the CLI and the API.

    from pokelike import session, play, compare

    with session() as game:            # a script: closed on the way out
        obs = game.reset(seed=42)

    game = open_game()                 # a notebook: stays alive between cells
    obs = game.reset(seed=42)
    ...
    game.close()

See `example.ipynb` in this folder for the cell-by-cell version.
"""

from .driver import compare, evaluate, format_comparison, open_game, play, session

__all__ = ["session", "open_game", "play", "evaluate", "compare", "format_comparison"]
