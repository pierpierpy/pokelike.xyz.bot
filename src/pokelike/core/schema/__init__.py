"""What a bot actually receives, described from a real observation.

In: nothing at the package level. Out: re-exports of all public names.

Hand-written documentation of a data structure goes stale the first time someone
adds a field and forgets the doc. This captures a live state instead and prints
the reference from it, so `pokelike schema` can never describe a game that no
longer exists.

    pokelike schema              # human readable reference
    pokelike schema --json       # a real observation, for poking at
    pokelike schema --markdown   # regenerates the reference inside STATE.md
"""

from .describe import as_markdown, capture, describe
from .fields import FIELDS, MAP_FIELDS, NODE_KINDS, RUN_FIELDS, TEAM_FIELDS

__all__ = [
    "FIELDS", "RUN_FIELDS", "TEAM_FIELDS", "MAP_FIELDS", "NODE_KINDS",
    "describe", "as_markdown", "capture",
]
