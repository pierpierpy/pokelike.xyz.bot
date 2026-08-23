"""What a bot receives, described from a live observation.

The schema is generated from a real state, so `pokelike schema` always reflects
the current game. Fields present in an observation but missing from the reference
are reported as undocumented.

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
