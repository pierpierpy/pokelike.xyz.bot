"""pokelike: play pokelike.xyz headless from Python, a CLI or an HTTP API.

    from pokelike import session, open_game, play, compare, create

    with session() as game:                       # a script
        obs = game.reset(seed=42)
        obs = game.step(0)

    game = open_game()                            # a notebook: survives the cell
    obs = game.reset(seed=42)

    play(create("sarsa-v2"), seed=42)             # one run, with its trace
    compare({"mine": create("mine")}, seeds=range(20))   # against random, paired

`create` takes the name of a folder under `bots/`, the same name `--bot` takes.
There is no module to import and nothing to register: a bot exists because its
directory does.

See `interfaces/python/example.ipynb` for the cell-by-cell walkthrough.
"""

from .bot import create
from .core.game import Game, IllegalAction
from .interfaces.python import compare, evaluate, open_game, play, session

__all__ = [
    "Game", "IllegalAction", "create",
    "session", "open_game", "play", "evaluate", "compare",
]
__version__ = "0.1.0"
