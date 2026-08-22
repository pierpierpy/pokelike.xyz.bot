"""Text rendering of the game state.

Everything here is rebuilt from `state`, a JavaScript object read as JSON. No
pixel is ever inspected: the map below is not read from an image, we draw it
ourselves from the nodes and edges.

This package re-exports every public name that was previously available as
`render.<name>`, so existing imports continue to work unchanged.
"""

from .actions import actions_view, tutor_view
from .screen import ending_view, screen, trace_line, trace_view
from .team import score_view, team_view
from .world import (
    ANSI,
    EMOJI,
    ICONS,
    LEGEND,
    exits_of,
    graph_view,
    map_view,
)

__all__ = [
    "exits_of",
    "ANSI",
    "EMOJI",
    "ICONS",
    "LEGEND",
    "actions_view",
    "ending_view",
    "graph_view",
    "map_view",
    "score_view",
    "screen",
    "team_view",
    "trace_line",
    "trace_view",
    "tutor_view",
]
