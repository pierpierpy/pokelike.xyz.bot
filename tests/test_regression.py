"""The regression net: recorded runs must replay identically.

If any of these fail after a refactor, behaviour changed. The fingerprint holds
only engine data, so renaming or translating our own strings cannot make the test
fail. Only a real change in how the game is played can.
"""

from __future__ import annotations

import pytest
from fingerprint import CASES, fingerprint, load_golden


@pytest.mark.slow
@pytest.mark.parametrize("seed,policy", CASES, ids=lambda v: str(v))
def test_run_matches_golden(game, seed, policy):
    expected = load_golden()[f"{seed}-{policy}"]
    got = fingerprint(game, seed, policy)

    # Compared field by field so a failure says *what* moved, not just "differs".
    assert got["steps"] == expected["steps"], "different number of decisions"
    assert got["final_screen"] == expected["final_screen"], "different ending"
    assert got["points"] == expected["points"], "different score"
    assert got["breakdown"] == expected["breakdown"], "different score breakdown"
    assert got["team"] == expected["team"], "different final team"
    assert got["trace"] == expected["trace"], "different sequence of decisions"


@pytest.mark.slow
def test_same_seed_same_run(game):
    """Determinism: replaying a seed with the same policy gives the same run."""
    a = fingerprint(game, 5, "fixed")
    b = fingerprint(game, 5, "fixed")
    assert a == b


@pytest.mark.slow
def test_different_seeds_different_runs(game):
    """Sanity check on the other side: the seed must actually matter."""
    a = fingerprint(game, 11, "cycling")
    b = fingerprint(game, 12, "cycling")
    assert a["trace"] != b["trace"]
