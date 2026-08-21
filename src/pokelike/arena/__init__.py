"""The bot competition: your code is the entry, the game is fixed.

    bench.py         the standard 50 seeds, and the result file that comes out
    scaffold.py      `pokelike bot new`: writes a folder that already plays
    leaderboard.py   reads the results, ranks them, and defines `Artifact`

An entry is a folder under `bots/`, and inside it the author decides everything:
the policy, the prompt, the view, the tools, even the bridge that says what is in
the state. The 50 seeds and `core/init.js` are the only fixed points, so the
standings rank ideas.

The other benchmark is `pokelike.harness`, where the scaffold is frozen and the
model is the only variable. Rows are never compared across the two.

`leaderboard.py` defines `Artifact`, imported by the frozen harnesses and the
submitted bots as `pokelike.arena.leaderboard.Artifact`. That import path is part
of what their fingerprints cover, so it stays put here.
"""
