"""How something outside drives the game.

This package provides two entry points, both thin faces over `core.game.Game`:

    cli/    a human, in a terminal
    api/    a program, over HTTP

The `bot/` package lives elsewhere because a bot is an extension point that
these interfaces run, rather than an entry point of its own.
"""
