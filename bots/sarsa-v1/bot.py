"""A trained SARSA(lambda) policy with linear function approximation, playing greedily.

    pokelike bot run --bot sarsa-v1 --runs 5
    pokelike bot bench --bot sarsa-v1 --category rl

    q̂(s, a, w) = wᵀ x(s, a)

Trained by `experiments/sarsa/`. Sutton & Barto, 2nd edition: chapter 10
for the semi-gradient control update, section 12.7 for the SARSA(lambda) form.

This is the first feature set (81 features, encoding v1). The feature code is
frozen in this file alongside the weights so the submission stays self-contained.
The FEATURES_VERSION constant is checked on load, and a mismatch raises an error.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

# Bumped whenever the feature vector changes meaning. Weights carry the version
# they were trained under; loading a mismatch raises an error.
FEATURES_VERSION = 1

# The weights live beside this file. POKELIKE_SARSA_WEIGHTS overrides for
# measuring a candidate before promotion.
HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "artifacts" / "weights.json"


def find_weights() -> Path | None:
    override = os.environ.get("POKELIKE_SARSA_WEIGHTS")
    return Path(override) if override else WEIGHTS


# ------------------------------------------------- the frozen feature set, v1

TYPES = {
    "NORMAL", "FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHTING", "POISON",
    "GROUND", "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST", "DRAGON", "DARK",
    "STEEL", "FAIRY",
}

NODE_KINDS = [
    "catch", "battle", "trainer", "item", "pokecenter", "question",
    "move_tutor", "trade", "boss", "pokemart", "shiny", "other",
]

SCREENS = [
    "catch-screen", "starter-screen", "item-screen", "item-equip-modal",
    "swap-screen", "trainer-screen", "other-screen",
]

RE_LEVEL = re.compile(r"Lv\.?\s*(\d+)")
RE_POWER = re.compile(r"(\d+)\s*PWR")
RE_HP = re.compile(r"\bHP\s+(\d+)")
RE_ATK = re.compile(r"\bATK\s+(\d+)")
RE_SPA = re.compile(r"SP\.A\s+(\d+)")
RE_DEF = re.compile(r"\bDEF\s+(\d+)")


def parse_pokemon(label: str) -> dict[str, Any]:
    """Extract level, types, and stats from a Pokemon card's label text."""
    up = label.upper()
    types = [t for t in TYPES if re.search(rf"\b{t}\b", up)]
    lvl = RE_LEVEL.search(label)
    pwr = RE_POWER.search(label)
    hp = RE_HP.search(label)
    atk = RE_ATK.search(label) or RE_SPA.search(label)
    dfn = RE_DEF.search(label)
    return {
        "types": types,
        "level": int(lvl.group(1)) if lvl else 0,
        "power": int(pwr.group(1)) if pwr else 0,
        "hp": int(hp.group(1)) if hp else 0,
        "atk": int(atk.group(1)) if atk else 0,
        "def": int(dfn.group(1)) if dfn else 0,
        "shiny": "★" in label or "SHINY" in up,
    }


def _team_types(team: list[dict]) -> set[str]:
    return {t.upper() for p in team for t in (p.get("types") or [])}


def _hp_fracs(team: list[dict]) -> list[float]:
    return [p["hp"] / p["max_hp"] for p in team if p.get("max_hp")]


def _depth_frac(state: dict[str, Any]) -> float:
    m = state.get("map")
    if not m or not m.get("current"):
        return 0.0
    layers = [n["layer"] for n in m["nodes"]]
    cur = next((n["layer"] for n in m["nodes"] if n["id"] == m["current"]), 0)
    return cur / max(layers) if layers and max(layers) else 0.0


def _leads_to(state: dict[str, Any], node_id: str) -> list[str]:
    m = state.get("map") or {}
    by_id = {n["id"]: n for n in m.get("nodes", [])}
    return [by_id[t]["kind"] for f, t in m.get("edges", []) if f == node_id and t in by_id]


def feature_names() -> list[str]:
    """The vector's index order, named."""
    names = [
        "bias", "team_size", "min_hp", "mean_hp", "map_index", "depth",
        "badges", "any_fainted", "n_actions",
    ]
    names += [f"node:{k}" for k in NODE_KINDS]
    names += [f"node:{k}*deep" for k in NODE_KINDS]
    names += [f"node:{k}*hurt" for k in NODE_KINDS]
    names += [f"node:{k}*small_team" for k in NODE_KINDS]
    names += ["leads_to_heal", "leads_to_catch", "leads_to_boss", "leads_dead_end"]
    names += [f"screen:{s}" for s in SCREENS]
    names += [
        "mon_new_type", "mon_level_rel", "mon_power", "mon_bulk", "mon_atk",
        "mon_shiny", "mon_best_stats",
        "equip_on_strongest", "equip_on_weakest", "swap_out_weakest",
        "is_skip", "is_cancel", "is_bag",
    ]
    return names


N_FEATURES = len(feature_names())
_NAME_INDEX = {n: i for i, n in enumerate(feature_names())}


def features(state: dict[str, Any], action: dict[str, Any]) -> dict[int, float]:
    """Sparse x(s, a): index -> value, non-zero entries only."""
    names = _NAME_INDEX
    x: dict[int, float] = {}

    def put(name: str, value: float = 1.0) -> None:
        if value:
            x[names[name]] = value

    run = state.get("run") or {}
    team = state.get("team") or []
    fracs = _hp_fracs(team)
    min_hp = min(fracs) if fracs else 0.0
    mean_hp = sum(fracs) / len(fracs) if fracs else 0.0
    depth = _depth_frac(state)
    small_team = 1.0 - min(len(team), 6) / 6

    put("bias")
    put("team_size", min(len(team), 6) / 6)
    put("min_hp", min_hp)
    put("mean_hp", mean_hp)
    put("map_index", min(run.get("map") or 0, 8) / 8)
    put("depth", depth)
    put("badges", min(run.get("badges") or 0, 8) / 8)
    put("any_fainted", 1.0 if run.get("anyone_fainted") else 0.0)
    put("n_actions", len(state.get("actions") or []) / 7)

    if action.get("kind") == "node":
        kind = action["node"] if action["node"] in NODE_KINDS else "other"
        put(f"node:{kind}")
        put(f"node:{kind}*deep", depth)
        put(f"node:{kind}*hurt", 1.0 - min_hp)
        put(f"node:{kind}*small_team", small_team)

        ahead = _leads_to(state, action["id"])
        put("leads_to_heal", 1.0 if "pokecenter" in ahead else 0.0)
        put("leads_to_catch", 1.0 if "catch" in ahead else 0.0)
        put("leads_to_boss", 1.0 if "boss" in ahead else 0.0)
        put("leads_dead_end", 1.0 if not ahead else 0.0)
        return x

    screen = action.get("layer") if action.get("layer") in SCREENS else "other-screen"
    put(f"screen:{screen}")
    label = action.get("label") or ""
    low = label.lower()

    put("is_skip", 1.0 if "skip" in low else 0.0)
    put("is_cancel", 1.0 if "cancel" in low else 0.0)
    put("is_bag", 1.0 if "keep in bag" in low else 0.0)

    if screen in ("catch-screen", "starter-screen"):
        mon = parse_pokemon(label)
        if mon["types"]:
            have = _team_types(team)
            put("mon_new_type", 1.0 if any(t not in have for t in mon["types"]) else 0.0)
        levels = [p["level"] for p in team] or [mon["level"] or 1]
        put("mon_level_rel", min(2.0, mon["level"] / max(1, sum(levels) / len(levels))) / 2)
        put("mon_power", min(mon["power"], 100) / 100)
        put("mon_bulk", min(mon["hp"], 40) / 40)
        put("mon_atk", min(mon["atk"], 40) / 40)
        put("mon_shiny", 1.0 if mon["shiny"] else 0.0)
        rivals = [parse_pokemon(o.get("label") or "") for o in state["actions"]]
        totals = [r["hp"] + r["atk"] + r["def"] for r in rivals]
        mine = mon["hp"] + mon["atk"] + mon["def"]
        put("mon_best_stats", 1.0 if totals and mine >= max(totals) else 0.0)
        return x

    if screen in ("item-equip-modal", "swap-screen") and team:
        # These screens list the team, so the option's position is the member.
        idx = action.get("idx", 0)
        if idx < len(team):
            atk_of = [p.get("base_stats", {}).get("atk", 0) for p in team]
            hp_of = [p["hp"] for p in team]
            strongest = max(range(len(team)), key=lambda i: atk_of[i])
            weakest = min(range(len(team)), key=lambda i: (team[i]["level"], hp_of[i]))
            put("equip_on_strongest", 1.0 if idx == strongest else 0.0)
            put("equip_on_weakest", 1.0 if idx == weakest else 0.0)
            # On the swap screen the listed Pokemon is the one released.
            if screen == "swap-screen":
                put("swap_out_weakest", 1.0 if idx == weakest else 0.0)
    return x


# ------------------------------------------------------------------- the bot


class SarsaBot(Bot):
    name = "sarsa-v1"

    def __init__(self, seed: int = 0, weights: str | Path | None = None) -> None:
        path = Path(weights) if weights else find_weights()
        if path is None or not path.is_file():
            raise FileNotFoundError(
                "no trained weights found. Looked in:\n  "
                + "\n  ".join(str(p) for p in WEIGHT_CANDIDATES)
                + "\n\ntrain some:  uv run python -m experiments.sarsa.train --episodes 300"
                + "\nor point at some:  POKELIKE_SARSA_WEIGHTS=/path/to/weights.json"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("encoding_version")
        if version != FEATURES_VERSION:
            raise ValueError(
                f"these weights were trained with feature set v{version}, and this "
                f"bot speaks v{FEATURES_VERSION}. The indices no longer point at the "
                f"same features, so w would be read as a different policy entirely: "
                f"retrain, or load them with a bot of the matching version."
            )
        stored = data.get("weights") or {}
        self.w = [float(stored.get(n, 0.0)) for n in feature_names()]
        self.weights_path = path
        self.trained_updates = data.get("updates", 0)
        self.rng = random.Random(seed)
        self.decisions = 0
        self._last_why = ""

    def reset(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def q(self, x: dict[int, float]) -> float:
        return sum(self.w[i] * v for i, v in x.items())

    def act(self, state: dict[str, Any]) -> int:
        """Greedy over q̂(s, a, w). Ties broken at random, seeded."""
        self.decisions += 1
        actions = state["actions"]
        values = [self.q(features(state, a)) for a in actions]
        best = max(values)
        self._last_why = "q: " + ", ".join(
            f"{self._tag(a, i)}={v:.1f}" for i, (a, v) in enumerate(zip(actions, values))
        )
        return self.rng.choice([i for i, v in enumerate(values) if v == best])

    @staticmethod
    def _tag(action: dict[str, Any], index: int) -> str:
        if action.get("kind") == "node":
            return str(action.get("node") or "node")
        label = (action.get("label") or "").strip().split("\n")[0]
        return (label[:14] or f"slot{index}").lower()

    def reason(self) -> str:
        return self._last_why

    def metadata(self) -> dict[str, Any]:
        """Recorded in the run registry and the benchmark result."""
        return {
            "weights": self.weights_path.name,
            "features_version": FEATURES_VERSION,
            "n_features": N_FEATURES,
            "training_updates": self.trained_updates,
            "decisions": self.decisions,
        }

    def top_weights(self, n: int = 12) -> list[tuple[str, float]]:
        pairs = sorted(zip(feature_names(), self.w), key=lambda p: -abs(p[1]))
        return [(name, round(w, 3)) for name, w in pairs[:n]]

    def artifacts(self) -> list:
        """The files a submission of this bot carries."""
        from pokelike.arena.leaderboard import Artifact

        stored = json.loads(self.weights_path.read_text(encoding="utf-8"))
        return [
            Artifact(
                name="weights.json",
                kind="weights-json",
                description=f"w, {N_FEATURES} named features, feature set v{FEATURES_VERSION}",
                path=self.weights_path,
            ),
            Artifact(
                name="config.json",
                kind="config",
                description="how the policy was trained",
                data={
                    "algorithm": "semi-gradient SARSA(lambda), linear FA (S&B ch. 10 and 12.7)",
                    "features_version": FEATURES_VERSION,
                    "n_features": N_FEATURES,
                    "hyperparameters": stored.get("hyperparameters"),
                    "updates": stored.get("updates"),
                    "trainer": "experiments/sarsa/train.py",
                    "top_weights": dict(self.top_weights(15)),
                },
            ),
        ]
