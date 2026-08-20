"""The bot competition: your code is the entry, the game is fixed.

    bench.py      the standard 50 seeds, and the result file that comes out
    scaffold.py   `pokelike bot new`: writes a folder that already plays

An entry is a folder under `bots/`, and inside it the author decides everything:
the policy, the prompt, the view, the tools, even the bridge that says what is in
the state. The 50 seeds and `core/init.js` are the only fixed points, so the
standings rank ideas.

The other benchmark is `pokelike.instrument`, where the scaffold is frozen and the
model is the only variable. Rows are never compared across the two.

Not in here, and deliberately: `pokelike.leaderboard`, which reads the results and
builds the standings. It also defines `Artifact`, which the frozen harnesses import,
and both they and the submitted bots are fingerprinted over files that contain that
import path. Moving it would change those files, which would mark every recorded
score as no longer describing what is on disk.
"""
