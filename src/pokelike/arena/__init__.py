"""The bot competition: your code is the entry, the game is fixed.

    bench/           the standard 50 seeds, and the result file that comes out:
                     seeds, run, progress, report
    scaffold.py      `pokelike bot new`: writes a folder that already plays
    leaderboard/     reads the results, ranks them, and defines `Artifact`:
                     artifact, record, table

An entry is a folder under `bots/`, and inside it the author decides everything:
the policy, the prompt, the view, the tools, even the bridge that says what is in
the state. The 50 seeds and `core/init.js` are the only fixed points, so the
standings rank ideas.

The other benchmark is `pokelike.harness`, where the scaffold is frozen and the
model is the only variable. Rows are never compared across the two.

`leaderboard/` defines `Artifact`, imported by the frozen harnesses and the
submitted bots as `pokelike.arena.leaderboard.Artifact`. That import path is part
of what their fingerprints cover, so it stays put here.
"""
