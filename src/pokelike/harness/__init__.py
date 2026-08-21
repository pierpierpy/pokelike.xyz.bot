"""The model benchmark: the scaffold is frozen, the model is the entry.

    llmbench/   versions and fingerprints, one pass and its log, the results and
                their tables, the pricing, the fan-out and its worker
    watch/      `pokelike model watch`: reading a pass's own trace, the per-pass
                dashboard and the overview of everything running

Every version under `llm-bench/<v>/harness/` freezes four files: the loop, the text
the model reads, the bridge that decides what is in the state, and the script that
pins the seed. So every model measured under a version was asked the same question,
and a row says something about the model rather than about whoever tuned a prompt.

Changing what is asked means a new version, not an edit. The old rows stay valid
under the version that earned them, which is why the version is in the path.

The other benchmark is `pokelike.arena`, where the author's code is the entry.
Rows are never compared across the two.
"""
