"""The feature sets being compared, and what each one is asking.

A variant is a question with an answer you can be wrong about, written down
before the run so the result cannot be reinterpreted afterwards into whatever
happened.

This module lives next to the agent it varies because the variants are all SARSA,
and a variant means nothing without the feature set in `features.py` that defines
the groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .groups import ALL_GROUPS, feature_names


@dataclass(frozen=True)
class Variant:
    name: str
    groups: list[str] | None          # None means every group
    question: str                     # what this run would settle
    expect: str                       # what I think happens, written down first

    @property
    def names(self) -> list[str]:
        return feature_names(self.groups)

    @property
    def n(self) -> int:
        return len(self.names)


# Groups that cannot tell two actions apart, because they read the state and
# never the action. See the README.
STATE_ONLY = ["context", "screen"]
ACTION_AWARE = [g for g in ALL_GROUPS if g not in STATE_ONLY]
INTERACTIONS = ["node_deep", "node_hurt", "node_team"]
# The three groups feature set v2 added. Measured against v1 on the standard 50
# seeds they bought +0.06 badges with t = 0.62, which is nothing. Whether those
# features are useless or merely drowned out is what `no-v2` asks.
V2_GROUPS = ["item", "tutor", "order"]


VARIANTS: list[Variant] = [
    Variant(
        name="full",
        groups=None,
        question="The control: the 100 features of set v2, the one on the leaderboard.",
        expect="About 1.36 badges. Everything else is measured against this.",
    ),
    Variant(
        name="action-only",
        groups=ACTION_AWARE,
        question=(
            "Do the state-only groups (context, screen) contribute anything to the "
            "POLICY? They cancel in the argmax, so in principle they cannot."
        ),
        expect=(
            "No worse than full, and possibly better: 16 fewer features means the "
            "traces and the step size are spent on features that can actually "
            "change a decision. If this LOSES, my reading of the weights is wrong "
            "and the state-only features are helping the bootstrapped target more "
            "than they cost."
        ),
    ),
    Variant(
        name="no-v2",
        groups=[g for g in ALL_GROUPS if g not in V2_GROUPS],
        question=(
            "Do the groups v2 added — team order, items, the move tutor — earn "
            "anything at all? Head to head on the standard seeds they bought "
            "+0.06 badges with t = 0.62, which is nothing."
        ),
        expect=(
            "No worse than full, and if it is genuinely EQUAL then those 19 "
            "features are dead weight and should be cut rather than kept for "
            "looking sensible. If full pulls ahead here while it did not on the "
            "benchmark, the gain is real but too small to see in 50 runs."
        ),
    ),
    Variant(
        name="no-interactions",
        groups=[g for g in ALL_GROUPS if g not in INTERACTIONS],
        question=(
            "Do the 36 node x situation crosses earn their keep, or is the plain "
            "node kind enough?"
        ),
        expect=(
            "Slightly worse than full. `node:trainer*small_team` was one of the "
            "few action-aware weights that grew large, which suggests at least one "
            "of the three crosses is doing real work."
        ),
    ),
    Variant(
        name="minimal",
        groups=["node", "mon", "lookahead"],
        question=(
            "How much of the result is carried by just three groups: what the node "
            "is, what the Pokemon on the card is, what lies one step ahead?"
        ),
        expect=(
            "Clearly worse, but well above random. If it comes close to full, then "
            "the other 55 features are decoration and the plateau is a shortage of "
            "signal, not an excess of it."
        ),
    ),
]

BY_NAME = {v.name: v for v in VARIANTS}


def describe() -> str:
    out = []
    for v in VARIANTS:
        groups = "all" if v.groups is None else "+".join(v.groups)
        out.append(f"{v.name}  ({v.n} features: {groups})")
        out.append(f"    asks:    {v.question}")
        out.append(f"    expects: {v.expect}")
        out.append("")
    return "\n".join(out)
