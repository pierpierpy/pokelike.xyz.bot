"""The representation: what the agent is allowed to see.

The features are split from the algorithm on purpose. Tabular Dyna-Q lost to
random on this game and its own logs said why (the table could not tell three
starters apart) so the lesson written into this package's existence is that the
representation is the part worth arguing about, not the update rule.

    groups.py     the 81 features, in named groups
    variants.py   which groups a given run carries, and what that run is asking
"""

from __future__ import annotations

from .groups import (
    ALL_GROUPS,
    GROUPS,
    N_FEATURES,
    NODE_KINDS,
    SCREENS,
    FeatureSet,
    feature_names,
    features,
    reorder_options,
    parse_pokemon,
)
from .variants import VARIANTS, BY_NAME, Variant, describe

__all__ = [
    "ALL_GROUPS", "GROUPS", "N_FEATURES", "NODE_KINDS", "SCREENS",
    "FeatureSet", "feature_names", "features", "parse_pokemon", "reorder_options",
    "VARIANTS", "BY_NAME", "Variant", "describe",
]
