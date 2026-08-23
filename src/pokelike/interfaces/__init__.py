"""How something outside drives the game.

Two entry points, both thin faces over `core.game.Game`:

    cli/    a human, in a terminal
    api/    a program, over HTTP

The `bot/` package lives elsewhere because it is an extension point, not an
entry point: you write a bot, and these interfaces run it.
"""
