"""A trained SARSA(lambda) policy with linear function approximation, playing greedily.

    pokelike bot run --bot sarsa-v2 --runs 5
    pokelike bot bench --bot sarsa-v2 --category rl

    q̂(s, a, w) = wᵀ x(s, a)

The weights were trained by `experiments/sarsa/`. See Sutton & Barto, 2nd edition,
chapter 10 for the semi-gradient control update, section 12.7 for the SARSA(lambda)
form.

This is the second feature set (100 features, encoding v2), adding type-matchup,
item, team-order, and move-tutor terms to sarsa-v1's 81.

The feature code is frozen in this file alongside the weights so the submission
stays self-contained. The FEATURES_VERSION constant is checked on load, and a
mismatch raises an error.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

# This version is bumped whenever the feature vector changes meaning. Weights
# carry the version they were trained under, and loading a mismatch raises an error.
#
# Version 2 added the order, items, and tutor groups relative to v1.
FEATURES_VERSION = 2

# The weights live beside this file. The POKELIKE_SARSA_WEIGHTS environment
# variable overrides this path for measuring a candidate before promotion.
HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "artifacts" / "weights.json"


def find_weights() -> Path:
    override = os.environ.get("POKELIKE_SARSA_WEIGHTS")
    return Path(override) if override else WEIGHTS


# ---------------------------------------------- the frozen feature set, v2
#
# This code is copied from experiments/sarsa/features/groups.py but is not
# imported, so the submission stays self-contained.

TYPES = {
    "NORMAL", "FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHTING", "POISON",
    "GROUND", "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST", "DRAGON", "DARK",
    "STEEL", "FAIRY",
}

# These node kinds each get their own feature; anything rarer falls into "other".
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


# The named feature groups are listed here. Group order defines index order and
# must not be reshuffled, because `w[i]` only means something because this list
# defines position i's name.
GROUPS: dict[str, list[str]] = {
    # These are state-only context features that cannot discriminate between
    # actions by construction.
    "context": ["bias", "team_size", "min_hp", "mean_hp", "map_index", "depth",
                "badges", "any_fainted", "n_actions"],
    # These encode which kind of node this move leads to.
    "node": [f"node:{k}" for k in NODE_KINDS],
    # These cross the node kind with the situation.
    "node_deep": [f"node:{k}*deep" for k in NODE_KINDS],
    "node_hurt": [f"node:{k}*hurt" for k in NODE_KINDS],
    "node_team": [f"node:{k}*small_team" for k in NODE_KINDS],
    # These encode one step of lookahead past the node.
    "lookahead": ["leads_to_heal", "leads_to_catch", "leads_to_boss", "leads_dead_end"],
    # These record which screen the choice is on (state-only).
    "screen": [f"screen:{s}" for s in SCREENS],
    # These encode Pokemon card stats.
    "mon": ["mon_new_type", "mon_level_rel", "mon_power", "mon_bulk", "mon_atk",
            "mon_shiny", "mon_best_stats"],
    # These indicate which team member a slot-shaped screen is pointing at.
    "slot": ["equip_on_strongest", "equip_on_weakest", "swap_out_weakest"],
    "button": ["is_skip", "is_cancel", "is_bag"],
    # Team order features. Slot 0 leads the next battle, and reordering does
    # not consume the turn. Features are relative to the current leader, so
    # they discriminate between candidates.
    #
    # Item features. The item screen's features read the id and TYPE_ITEM_MAP
    # (the engine's type-to-item table).
    "item": [
        "item:matches_my_type",
        "item:matches_lead_type",
        "item:is_evolution",
        "item:is_healing",
        "item:is_defensive",
        "item:is_offensive",
        "item:already_held",
    ],
    # The move tutor features compare the offered move against what the recipient
    # uses now.
    "tutor": [
        "tutor:power_gain",
        "tutor:is_upgrade",
        "tutor:on_lead",
        "tutor:on_strongest",
        "tutor:same_type",
    ],
    "order": [
        "order:noop",
        "order:hp_gain",
        "order:swap_when_lead_hurt",
        "order:cand_level_rel",
        "order:cand_is_strongest",
        "order:cand_new_type",
        "order:cand_fainted",
    ],
}

ALL_GROUPS = list(GROUPS)


def feature_names(groups: list[str] | None = None) -> list[str]:
    """Return the vector's index order as a list of names.

    This function returns the full set when called with no argument.
    """
    for g in (groups or []):
        if g not in GROUPS:
            raise KeyError(f"unknown feature group '{g}' — have: {', '.join(ALL_GROUPS)}")
    chosen = ALL_GROUPS if groups is None else [g for g in ALL_GROUPS if g in groups]
    return [n for g in chosen for n in GROUPS[g]]


N_FEATURES = len(feature_names())


def features(state: dict[str, Any], action: dict[str, Any],
             index: dict[str, int] | None = None) -> dict[int, float]:
    """Return sparse x(s, a) as a dict of index to value, non-zero entries only.

    When `index` is provided, names not present in the dict are silently skipped,
    which is how a variant with some groups switched off works.
    """
    names = _NAME_INDEX if index is None else index
    x: dict[int, float] = {}

    def put(name: str, value: float = 1.0) -> None:
        # The function silently skips names that the variant left out.
        i = names.get(name)
        if value and i is not None:
            x[i] = value

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

    if action.get("kind") == "reorder":
        # A value of None for b means "leave it"; otherwise b identifies the
        # slot to bring to front.
        b = action.get("b")
        if b is None or not team:
            put("order:noop")
            return x
        lead, cand = team[0], team[b] if b < len(team) else team[0]
        frac = lambda p: (p["hp"] / p["max_hp"]) if p.get("max_hp") else 0.0
        levels = [p["level"] for p in team] or [1]
        atks = [p.get("base_stats", {}).get("atk", 0) for p in team]

        put("order:hp_gain", frac(cand) - frac(lead))
        put("order:swap_when_lead_hurt", 1.0 - frac(lead))
        put("order:cand_level_rel",
            min(2.0, cand["level"] / max(1, sum(levels) / len(levels))) / 2)
        put("order:cand_is_strongest",
            1.0 if atks and atks[b] >= max(atks) else 0.0)
        lead_types = {t.upper() for t in (lead.get("types") or [])}
        put("order:cand_new_type",
            1.0 if any(t.upper() not in lead_types for t in (cand.get("types") or [])) else 0.0)
        put("order:cand_fainted", 1.0 if cand["hp"] == 0 else 0.0)
        return x

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

    if screen == "item-screen":
        _item_features(put, state, action)
    elif "→" in label or "->" in label:
        _tutor_features(put, state, action, label)

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
        # Whether this option has the highest combined stats on offer.
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


_NAME_INDEX = {n: i for i, n in enumerate(feature_names())}


class FeatureSet:
    """A variant of the vector that defines which groups are active and their
    index order.

    Weights are saved by name, so loading into a different group set zero-fills
    the missing ones.
    """

    def __init__(self, groups: list[str] | None = None) -> None:
        self.groups = list(ALL_GROUPS if groups is None else
                           [g for g in ALL_GROUPS if g in groups])
        self.names = feature_names(self.groups)
        self.index = {n: i for i, n in enumerate(self.names)}
        self.n = len(self.names)

    def of(self, state: dict[str, Any], action: dict[str, Any]) -> dict[int, float]:
        return features(state, action, self.index)

    def __repr__(self) -> str:
        return f"FeatureSet({self.n} features, groups={'+'.join(self.groups)})"


def reorder_options(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the team-order decision as a list of actions scored like any other.

    The list leads with the "leave it" option so that option competes on the same
    footing. The function returns an empty list when there is nothing to decide.
    """
    team = state.get("team") or []
    if not state.get("can_reorder") or len(team) < 2:
        return []
    return [{"kind": "reorder", "b": None}] + [
        {"kind": "reorder", "b": j} for j in range(1, len(team))
    ]


# These sets categorize items by effect, keyed on the item id. The engine has
# no structured effect field, so only the coarse kind is encoded here.
EVOLUTION_ITEMS = {"moon_stone", "fire_stone", "water_stone", "thunder_stone",
                   "leaf_stone", "sun_stone", "dusk_stone", "shiny_stone",
                   "dawn_stone", "ice_stone", "rare_candy"}
HEALING_ITEMS = {"leftovers", "shell_bell", "sitrus_berry", "oran_berry",
                 "sacred_ash", "black_sludge"}
DEFENSIVE_ITEMS = {"assault_vest", "eviolite", "red_card", "rocky_helmet",
                   "focus_sash", "leftovers", "shell_bell"}
OFFENSIVE_ITEMS = {"choice_band", "choice_specs", "choice_scarf", "life_orb",
                   "expert_belt", "muscle_band", "wise_glasses", "quick_claw",
                   "scope_lens", "razor_claw"}


def _item_id(action: dict[str, Any]) -> str:
    """Derive an item id from the button's label text."""
    label = (action.get("label") or "").strip().lower()
    words = re.split(r"[^a-z]+", label)
    return "_".join(w for w in words[:2] if w)


def _item_features(put, state: dict[str, Any], action: dict[str, Any]) -> None:
    item = _item_id(action)
    team = state.get("team") or []
    type_items = state.get("type_items") or {}
    # The TYPE_ITEM_MAP maps Pokemon type to item id; inverting the map reveals
    # which type this item boosts.
    boosts = {v: k.upper() for k, v in type_items.items()}
    boosted = boosts.get(item)

    if boosted and team:
        put("item:matches_my_type",
            1.0 if any(boosted in {t.upper() for t in (p.get("types") or [])}
                       for p in team) else 0.0)
        put("item:matches_lead_type",
            1.0 if boosted in {t.upper() for t in (team[0].get("types") or [])} else 0.0)

    put("item:is_evolution", 1.0 if item in EVOLUTION_ITEMS else 0.0)
    put("item:is_healing", 1.0 if item in HEALING_ITEMS else 0.0)
    put("item:is_defensive", 1.0 if item in DEFENSIVE_ITEMS else 0.0)
    put("item:is_offensive", 1.0 if item in OFFENSIVE_ITEMS else 0.0)
    held = {p.get("item_id") for p in team} | {
        (b or {}).get("id") for b in (state.get("bag_items") or [])
    }
    put("item:already_held", 1.0 if item in held else 0.0)


def _tutor_features(put, state: dict[str, Any], action: dict[str, Any],
                    label: str) -> None:
    """Compare the offered move against what the recipient currently uses.

    The label format is "-> SURF:Wartortle Lv35" or similar.
    """
    team = state.get("team") or []
    if not team:
        return
    who = None
    for i, p in enumerate(team):
        if p["name"].lower() in label.lower():
            who = i
            break
    if who is None:
        return
    mon = team[who]
    current = (mon.get("move") or {})
    offered = (state.get("offered_moves") or {}).get(str(who)) or {}
    cur_pw, new_pw = current.get("power") or 0, offered.get("power") or 0

    if new_pw or cur_pw:
        put("tutor:power_gain", max(-1.0, min(1.0, (new_pw - cur_pw) / 60)))
        put("tutor:is_upgrade", 1.0 if new_pw > cur_pw else 0.0)
    put("tutor:on_lead", 1.0 if who == 0 else 0.0)
    atks = [p.get("base_stats", {}).get("atk", 0) for p in team]
    put("tutor:on_strongest", 1.0 if atks and atks[who] >= max(atks) else 0.0)
    if offered.get("type"):
        put("tutor:same_type",
            1.0 if offered["type"].upper() in {t.upper() for t in (mon.get("types") or [])}
            else 0.0)


# ------------------------------------------------------------------- the bot


class SarsaBot(Bot):
    name = "sarsa-v2"

    def __init__(self, seed: int = 0, weights: str | Path | None = None) -> None:
        path = Path(weights) if weights else find_weights()
        if not path.is_file():
            raise FileNotFoundError(
                f"no weights at {path}.\n"
                "They ship next to this file, so this usually means the folder was "
                "copied without its artifacts/.\n"
                "To play a different set:  POKELIKE_SARSA_WEIGHTS=/path/to/weights.json"
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
        """Choose greedily over q̂(s, a, w), breaking ties at random with the seeded RNG."""
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

    def reorder(self, state: dict[str, Any]) -> tuple[int, int] | None:
        """Pick who leads the next battle, scored by the same q̂ weights."""
        options = reorder_options(state)
        if not options:
            return None
        values = [self.q(features(state, o)) for o in options]
        best = max(values)
        i = self.rng.choice([k for k, v in enumerate(values) if v == best])
        b = options[i]["b"]
        if b is None:
            return None
        team = state.get("team") or []
        self._last_why = (f"lead: {team[b]['name'] if b < len(team) else b} "
                          f"({values[i]:.1f}) over staying ({values[0]:.1f})")
        return (0, b)

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
