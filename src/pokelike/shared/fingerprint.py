"""This module provides code and behaviour fingerprints in one shared place.

`arena/` (the bot arena) and `utils/refingerprint.py` (outside the
package entirely) both need this exact logic, and neither should import it
from the other. This module is imported by both instead.

The module provides two hashes that serve different purposes.

The `code_fingerprint(bot_dir)` function hashes bytes, which identifies which
files played. A comment edit and a logic change both change the fingerprint,
because a file hash cannot tell them apart.

The `behaviour_hash(game)` function plays a short deterministic replay (fixed
seeds, scripted policies, no model, no randomness) and hashes only engine data
from the result, which identifies whether a decision moved. Two versions of the
code that decide every replay identically produce the same behaviour hash,
whatever changed in between; one version that moved a real decision does not.

The BEHAVIOUR_SCHEMA constant versions this module's own output shape rather
than the game's. Bump the constant when CASES or what a case records changes,
so a schema change is never mistaken for the game's own behaviour changing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BEHAVIOUR_SCHEMA = 1

# These four (seed, policy) pairs match the regression suite in
# tests/fingerprint.py, which already proved they catch real behavioural
# regressions. Playing more would only add wall clock without adding certainty.
CASES = [(1, "fixed"), (2, "fixed"), (3, "cycling"), (7, "cycling")]


# ---------------------------------------------------------------- code hash


def code_fingerprint(bot_dir: str | Path) -> str:
    """Returns a single hash over bot.py and every file in artifacts/.

    Each file is hashed together with its relative path, so renaming a file
    changes the fingerprint too.
    """
    bot_dir = Path(bot_dir)
    h = hashlib.sha256()
    files = [bot_dir / "bot.py", *sorted((bot_dir / "artifacts").glob("**/*"))]
    for f in files:
        if not f.is_file():
            continue
        h.update(str(f.relative_to(bot_dir)).encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()


# ------------------------------------------------------------- behaviour hash


def _policy_fixed(state: dict[str, Any]) -> int:
    """This policy always returns the first legal action."""
    return 0


def _policy_cycling(state: dict[str, Any]) -> int:
    """This policy cycles through the options so the run does not hug one branch."""
    return state["steps"] % len(state["actions"])


_POLICIES = {"fixed": _policy_fixed, "cycling": _policy_cycling}


def _stable_action(a: dict[str, Any]) -> str:
    """Returns a label for one action that survives a wording change but not a real one.

    Node actions are named by their engine id and kind. Other actions use the
    game's own button label, since the label decides which action an index
    actually points at. Leading decoration (a sprite fallback pictograph) is
    stripped because whether the pictograph renders depends on which assets
    happen to be on disk, not on the run itself.
    """
    if a.get("kind") == "node":
        return f"{a['id']}:{a['node']}"
    label = (a.get("label") or "").lstrip()
    while label and not label[0].isalnum():
        label = label[1:].lstrip()
    return f"el{a['idx']}:{label[:40]}"


def replay(game, seed: int, policy: str, max_steps: int = 120) -> dict[str, Any]:
    """Plays one deterministic run and returns what it produced.

    The result contains only engine data (screen ids, node types, the game's
    own labels, and scores). A wording change in this codebase can never show
    up here, but a decision that actually moved always does.
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

    The `game` argument must already be reset to the engine (bridge.js, init.js)
    whose behaviour is being checked. This function does not construct a Game,
    since a frozen llm-bench harness and a bot's own artifacts/bridge.js each
    build their Game differently. See `behaviour_hash_for` to build and tear
    one down in one call.
    """
    replays = [replay(game, seed, policy) for seed, policy in (cases or CASES)]
    blob = json.dumps(replays, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def behaviour_hash_for(site, **game_kwargs) -> str:
    """Builds a Game against `site`, plays the replay through the Game, and tears it down.

    This is the single place that opens an AssetServer and a Game for a
    behaviour check, so a harness version and a bot's own bridge share the
    plumbing instead of repeating the server-start/game-open/try-finally
    sequence independently. The `game_kwargs` parameter is whatever Game needs
    beyond `url` (typically `bridge=` and/or `init=`; when neither is given the
    function plays the shared, live pair).
    """
    from ..assets.server import AssetServer
    from ..core.game import Game
    from ..interfaces.python.driver.session import free_port

    server = AssetServer(site, port=free_port())
    server.start()
    game = Game(url=server.url, **game_kwargs)
    try:
        game.open()
        return behaviour_hash(game)
    finally:
        game.close()
        server.stop()
