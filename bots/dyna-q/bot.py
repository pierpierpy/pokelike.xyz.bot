"""A trained Dyna-Q policy, playing greedily.

    pokelike bot run --bot dyna-q --runs 5
    pokelike bot bench --bot dyna-q --category rl

This file is the EXAMPLE OF WHAT A SUBMISSION LOOKS LIKE, and it is deliberately
self-contained: the state and action encoding is copied in here rather than
imported from `experiments/dyna-q/`.

That is not duplication by accident. A policy is only meaningful under the exact
encoding it was trained with. If this file imported the training code, improving
the training code would silently change what every previously
submitted policy means, and old leaderboard entries would quietly become wrong.
Freezing the encoding next to the weights is what keeps a submission valid
forever.

`ENCODING_VERSION` is checked against the one stored in the table, so a mismatch
is an error rather than a bot that plays badly for reasons nobody can see.
"""

from __future__ import annotations

import json
import random
from ast import literal_eval
from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

# Every encoding this bot can speak. A table carries the version it was trained
# with, and old submissions must keep working: that is the whole point of
# freezing the encoding next to the weights, so both live here side by side.
LATEST_ENCODING = 2

# Its own folder, and nothing else. A bot is self-contained: the table sits
# beside the code that reads it. POKELIKE_DYNAQ_TABLE still overrides, which is
# how a candidate is measured before it is promoted.
HERE = Path(__file__).resolve().parent
TABLE = HERE / "artifacts" / "weights.json"


def find_table() -> Path:
    import os

    override = os.environ.get("POKELIKE_DYNAQ_TABLE")
    return Path(override) if override else TABLE


HP_THRESHOLDS = ((0.25, 0), (0.5, 1), (0.8, 2))


# ------------------------------------------------------- the frozen encoding


def hp_bucket(team: list[dict]) -> int:
    if not team:
        return 0
    alive = [p["hp"] / p["max_hp"] for p in team if p["max_hp"]]
    if not alive:
        return 0
    worst = min(alive)
    for threshold, bucket in HP_THRESHOLDS:
        if worst < threshold:
            return bucket
    return 3


def depth_bucket(state: dict[str, Any]) -> int:
    m = state.get("map")
    if not m or not m.get("current"):
        return 0
    layers = [n["layer"] for n in m["nodes"]]
    current = next((n["layer"] for n in m["nodes"] if n["id"] == m["current"]), 0)
    deepest = max(layers) if layers else 1
    frac = current / deepest if deepest else 0.0
    return 0 if frac < 0.34 else (1 if frac < 0.67 else 2)


def action_key(a: dict[str, Any]) -> str:
    if a.get("kind") == "node":
        return f"node:{a['node']}"
    label = (a.get("label") or "").strip().lower()
    for word, key in (("skip", "skip"), ("cancel", "cancel"),
                      ("keep in bag", "bag"), ("equip", "equip")):
        if word in label:
            return f"btn:{key}"
    return f"{a.get('layer', 'x')}:slot{a.get('idx', 0)}"


def _base_key(state: dict[str, Any]) -> tuple:
    run = state.get("run") or {}
    team = state.get("team") or []
    return (
        state.get("screen"),
        min(len(team), 6),
        hp_bucket(team),
        min(run.get("map") or 0, 8),
        depth_bucket(state),
        min(run.get("badges") or 0, 8),
    )


def state_key_v1(state: dict[str, Any]) -> tuple:
    """Version 1 also keyed on which actions were on offer.

    It fragmented the table badly — 563 states holding 686 state-action pairs,
    so barely more than one action per state — which is why version 2 dropped it.
    Kept so tables trained under v1 still play.
    """
    offered = tuple(sorted({action_key(a) for a in state.get("actions") or []}))
    return _base_key(state) + (offered,)


def state_key_v2(state: dict[str, Any]) -> tuple:
    """Version 2: the menu is left out, since Q is keyed by action anyway."""
    return _base_key(state)


ENCODINGS = {1: state_key_v1, 2: state_key_v2}


# ------------------------------------------------------------------ the bot


class DynaQBot(Bot):
    name = "dyna-q"

    def __init__(self, seed: int = 0, table: str | Path | None = None) -> None:
        path = Path(table) if table else find_table()
        if not path.is_file():
            raise FileNotFoundError(
                f"no table at {path}.\n"
                "It ships next to this file, so this usually means the folder was "
                "copied without its artifacts/.\n"
                "To play a different one:  POKELIKE_DYNAQ_TABLE=/path/to/table.json"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("encoding_version")
        if version not in ENCODINGS:
            raise ValueError(
                f"the table was trained with encoding version {version}, which this "
                f"bot does not speak (it knows {sorted(ENCODINGS)}). The states would "
                f"not mean the same thing, so the policy would be nonsense: retrain."
            )
        self.encoding_version = version
        self.state_key = ENCODINGS[version]

        self.Q: dict[tuple, dict[str, float]] = {
            literal_eval(s): v for s, v in data["Q"].items()
        }
        self.rng = random.Random(seed)
        self.table_path = path
        self.unseen = 0      # how often we fell back, worth knowing
        self.decisions = 0
        self._last_why = ""

    def on_start(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def notes(self) -> dict[str, Any]:
        """Goes into the run registry and the benchmark result."""
        return {
            "table": self.table_path.name,
            "encoding_version": self.encoding_version,
            "states_known": len(self.Q),
            "decisions": self.decisions,
            "unseen_states": self.unseen,
        }

    def artifacts(self) -> list:
        """What a submission of this bot must carry with it.

        The weights alone are not enough to understand a result: the encoding
        version says what the states mean, and without the training config the
        score is a number nobody can reproduce or improve on.
        """
        from pokelike.arena.leaderboard import Artifact

        table = json.loads(self.table_path.read_text(encoding="utf-8"))
        return [
            Artifact(
                name="weights.json",
                kind="weights-json",
                description=f"Q-table, {len(self.Q)} states, encoding v{self.encoding_version}",
                path=self.table_path,
            ),
            Artifact(
                name="config.json",
                kind="config",
                description="how the policy was trained",
                data={
                    "algorithm": "tabular Dyna-Q (Sutton & Barto 8.2)",
                    "encoding_version": self.encoding_version,
                    "hyperparameters": table.get("hyperparameters"),
                    "updates": table.get("updates"),
                    "states": len(self.Q),
                    "trainer": "experiments/dyna-q/train.py",
                },
            ),
        ]

    def explain(self) -> str:
        return self._last_why

    def choose(self, state: dict[str, Any]) -> int:
        self.decisions += 1
        actions = state["actions"]
        s = self.state_key(state)
        values = self.Q.get(s)

        if not values:
            # A state never met in training. Falling back is not cheating, it is
            # what any tabular policy has to do outside its table, and counting
            # how often it happens tells you whether training covered enough.
            self.unseen += 1
            self._last_why = "state never seen in training, fell back to the safe rule"
            return self._fallback(state)

        scored = [(values.get(action_key(a), 0.0), i) for i, a in enumerate(actions)]
        best = max(v for v, _ in scored)
        self._last_why = "Q: " + ", ".join(
            f"{action_key(a).split(':')[-1]}={values.get(action_key(a), 0.0):.1f}"
            for a in actions
        )
        return self.rng.choice([i for v, i in scored if v == best])

    @staticmethod
    def _fallback(state: dict[str, Any]) -> int:
        """Keep the team alive: heal if hurt, otherwise grow the team."""
        actions = state["actions"]
        team = state.get("team") or []
        hurt = [p for p in team if p["max_hp"] and p["hp"] / p["max_hp"] < 0.4]
        order = ["pokecenter", "catch", "item"] if hurt else ["catch", "item", "pokecenter"]
        for kind in order:
            for i, a in enumerate(actions):
                if a.get("node") == kind:
                    return i
        return 0
