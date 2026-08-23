"""Behaviour fingerprint: does the engine still decide the same thing?

A file hash (see `versions.fingerprints` and `utils/refingerprint.py`) answers
"which bytes played this", not "could this have changed a score". A comment
edit and a logic change produce two different hashes over the same file, and
today's fingerprint cannot tell them apart, so both get reported the same way.

This module answers the second question directly, by playing a short replay
with a deterministic policy (no model, no randomness) and hashing the result.
Two runs of the same code, same seed, same policy always produce the same
replay, so the same code always produces the same `behaviour_hash`; two
versions of the code that decide moves identically produce it too, even if
every comment and variable name in between changed.

BEHAVIOUR_SCHEMA is a version of this function's own output shape, not of the
game. Bump it when CASES or what a case records changes, so a schema change
cannot be mistaken for the game's own behaviour changing.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

BEHAVIOUR_SCHEMA = 1

# Same four (seed, policy) pairs as tests/fingerprint.py's regression suite,
# on purpose: that file already proved they are enough to catch a real
# behavioural regression (it is what let this repo be translated end to end
# with proof that nothing moved), and playing more would only add wall clock
# without adding certainty for what this checks.
CASES = [(1, "fixed"), (2, "fixed"), (3, "cycling"), (7, "cycling")]


def _policy_fixed(state: dict[str, Any]) -> int:
    """Always the first legal action."""
    return 0


def _policy_cycling(state: dict[str, Any]) -> int:
    """Cycles through the options, so the run does not hug one branch."""
    return state["steps"] % len(state["actions"])


_POLICIES = {"fixed": _policy_fixed, "cycling": _policy_cycling}


def _stable_action(a: dict[str, Any]) -> str:
    """A label for one action that survives a wording change but not a real one.

    Node actions are named by their engine id and kind, never our own text.
    Other actions use the game's own button label, since that is what decides
    which action an index actually points at; leading decoration (a sprite
    fallback pictograph) is stripped because whether it renders depends on
    which assets happen to be on disk, not on the run itself.
    """
    if a.get("kind") == "node":
        return f"{a['id']}:{a['node']}"
    label = (a.get("label") or "").lstrip()
    while label and not label[0].isalnum():
        label = label[1:].lstrip()
    return f"el{a['idx']}:{label[:40]}"


def replay(game, seed: int, policy: str, max_steps: int = 120) -> dict[str, Any]:
    """Plays one deterministic run and returns what it produced.

    Only engine data: screen ids, node types, the game's own labels, scores. No
    text this codebase writes itself, so a wording change can never show up
    here, and a decision that actually moved always does.
    """
    choose = _POLICIES[policy]
    obs = game.reset(seed=seed)
    trace: list[str] = []
    while not obs.get("done") and obs.get("actions") and game.steps < max_steps:
        i = choose(obs)
        trace.append(f"{obs['screen']}|{len(obs['actions'])}|{_stable_action(obs['actions'][i])}")
        obs = game.step(i)
    s = game.score() or {}
    alive = game.last_alive or obs
    return {
        "seed": seed,
        "policy": policy,
        "steps": game.steps,
        "final_screen": obs.get("screen"),
        "points": s.get("points_no_time"),
        "breakdown": s.get("breakdown"),
        "team": [
            {"name": m["name"], "level": m["level"], "hp": m["hp"], "max_hp": m["max_hp"]}
            for m in (alive.get("team") or [])
        ],
        "trace": trace,
    }


def behaviour_hash(game, cases: list[tuple[int, str]] | None = None) -> str:
    """Plays every case and returns one sha256 over all of them, sorted and stable.

    `game` must already be reset to the engine (bridge.js, init.js) whose
    behaviour is being checked; this function does not construct one, since a
    frozen llm-bench harness and a bot's own artifacts/bridge.js each build
    their `Game` differently.
    """
    replays = [replay(game, seed, policy) for seed, policy in (cases or CASES)]
    blob = json.dumps(replays, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
