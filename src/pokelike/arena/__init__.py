"""The bot arena, where the author's code is the entry and the game is fixed.

Submodules:

- bench/         the standard 50-seed benchmark and the result file it produces
                 (seeds, run, progress, report)
- scaffold.py    the ``pokelike bot new`` command, which writes a folder that
                 already plays
- leaderboard/   reads the results, ranks them, and defines ``Artifact``
                 (artifact, record, table)

An entry is a folder under ``bots/``, and inside it the author decides
everything: the policy, the prompt, the view, the tools, and even the bridge
that defines what is in the state. The 50 seeds and ``core/init.js`` are the
only fixed points, so the standings rank ideas.

The other benchmark is ``pokelike.harness``, where the harness is frozen and the
model is the only variable. Rows are never compared across the two.

The ``leaderboard/`` directory defines ``Artifact``, imported by the frozen
harnesses and the submitted bots as ``pokelike.arena.leaderboard.Artifact``.
That import path is part of what their fingerprints cover, so it stays put here.
"""
