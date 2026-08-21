"""A network scoring the same features sarsa-v2 scores with a dot product.

    uv run pokelike bot bench --bot experiments/drrn --dry-run

    q̂(s, a) = MLP(x(s, a))          against        q̂(s, a) = wᵀ x(s, a)

Trained by `experiments/drrn/`: transitions collected in parallel, then fitted
Q iteration offline. One variable moved from sarsa-v2 — the shape of q̂ — so
the difference between their benchmark numbers is the difference between a
linear model and a network on identical inputs.

WHY IT MIGHT HELP
-----------------
Most of the linear model's learned weight sits on features that read the same
for every action in a state, so they cancel in the argmax and cannot change a
choice. Removing them does not help either (measured: 1.36 against 1.38). What
they are is a term that only means something CROSSED with the action — how much
a trainer node is worth depends on how small the team is. The linear model can
only carry such a cross if someone writes it by hand, and three are written by
hand. A hidden layer builds them from the same inputs without anyone choosing.

WHY THE FEATURE CODE IS COPIED IN HERE
--------------------------------------
A parameter vector means nothing without the exact function that produced the
vectors it consumes: index 43 is a number, and only `feature_names()` says it
is `mon_new_type`. If this file imported `experiments/sarsa/features/`, then
inserting one feature there would shift every index and silently reinterpret
every policy ever submitted, including ones on the leaderboard.

A submission also archives ONE file and hashes it. Split the features into a
second module and the archive keeps an unrunnable half while the hash stops
identifying what actually ran.

So `FEATURES_VERSION` is frozen next to the weights and `ARCH_VERSION` next to
the shape; both are checked on load, and a mismatch is an error rather than a
bot that plays badly for reasons nobody can see.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

# Bumped whenever the feature vector changes meaning: a new feature, a removed
# one, a different order, a different scale. Weights carry the version they were
# trained under, and refusing to load a mismatch is the whole safeguard.
#
# 2 added three groups — team order, items, and the move tutor — so a v1 weight
# vector indexes an entirely different space.
FEATURES_VERSION = 2

# Its own folder, and nothing else. A bot is self-contained: the weights sit
# beside the code that reads them, so moving the folder moves the bot, and there
# is no lookup that can quietly hand this file somebody else's numbers.
#
# While the experiment is running, `output/models/` is where training writes and
# `artifacts/` is what the benchmark reads, so promoting a candidate is a copy
# you make on purpose.
HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "artifacts" / "weights.json"


def find_weights() -> Path:
    override = os.environ.get("POKELIKE_DRRN_WEIGHTS")
    return Path(override) if override else WEIGHTS


# ---------------------------------------------- the frozen feature set, v2
#
# Copied MECHANICALLY from experiments/sarsa/features/groups.py, never
# transcribed by hand, and pinned to it by a test. Hand-copying is how two
# feature sets drift apart while both look right.

TYPES = {
    "NORMAL", "FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHTING", "POISON",
    "GROUND", "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST", "DRAGON", "DARK",
    "STEEL", "FAIRY",
}

# Node kinds worth a feature of their own. Anything rarer falls into `other`.
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
    """Pull what matters out of a Pokemon card's text.

    The catch screen renders 'Psyduck Lv. 4 WATER SP.A 10 SPE 9 HP 18 DEF 8 ...'.
    All of it is on screen and none of it reached the tabular agent.
    """
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


# The vector, split into named groups so a variant can switch one off and the
# rest keep their meaning. GROUP ORDER IS THE INDEX ORDER and must not be
# reshuffled: a weight vector is a plain list, and `w[43]` means `mon_new_type`
# only because this list says so.
#
# The groups exist because of what the first trained policy turned out to look
# like. Its heaviest weights were all in `context` — features that depend on the
# state but not on the action, so they shift every option by the same amount and
# CANCEL in the argmax. They fit the level of the return, not the choice. That is
# a hypothesis you can only test by taking them away, which is what this is for.
GROUPS: dict[str, list[str]] = {
    # State only. Cannot discriminate between actions, by construction.
    "context": ["bias", "team_size", "min_hp", "mean_hp", "map_index", "depth",
                "badges", "any_fainted", "n_actions"],
    # Which kind of node this move leads to.
    "node": [f"node:{k}" for k in NODE_KINDS],
    # The same, crossed with the situation: 36 features earning their keep or not.
    "node_deep": [f"node:{k}*deep" for k in NODE_KINDS],
    "node_hurt": [f"node:{k}*hurt" for k in NODE_KINDS],
    "node_team": [f"node:{k}*small_team" for k in NODE_KINDS],
    # One step of lookahead past the node.
    "lookahead": ["leads_to_heal", "leads_to_catch", "leads_to_boss", "leads_dead_end"],
    # Which screen the choice is on. State only as well.
    "screen": [f"screen:{s}" for s in SCREENS],
    # What is actually on the card: the part the tabular agent could not see.
    "mon": ["mon_new_type", "mon_level_rel", "mon_power", "mon_bulk", "mon_atk",
            "mon_shiny", "mon_best_stats"],
    # Which team member a slot-shaped screen is pointing at.
    "slot": ["equip_on_strongest", "equip_on_weakest", "swap_out_weakest"],
    "button": ["is_skip", "is_cancel", "is_bag"],
    # Team order. A separate decision, not one of the game's actions: slot 0
    # leads the next battle but reordering does not consume the turn. The
    # options are "leave it" plus "bring slot j to the front".
    #
    # Every feature here is written as a DIFFERENCE against the current leader,
    # or as an interaction with `noop`. A feature that reads the same for the
    # leave-it option and for every swap would add the same number to all of
    # them and cancel in the argmax — which is exactly the mistake the ablation
    # was built to catch.
    # Items. Until now there were none at all, which is why the item screen
    # produced three identical q-values: the agent was choosing at random among
    # a Red Card, a Moon Stone and an Assault Vest.
    #
    # Effects are not structured data anywhere — an item is {id, name, desc,
    # icon} and every magnitude is inline in the battle code, keyed on the
    # string id. So these read the two things that ARE structured: the id, and
    # TYPE_ITEM_MAP, the engine's own type -> item table, which collapses
    # eighteen near-identical "+40% X-type damage" items into one question.
    "item": [
        "item:matches_my_type",   # boosts a type someone on my team actually is
        "item:matches_lead_type",
        "item:is_evolution",      # moon stone and friends: a permanent upgrade
        "item:is_healing",
        "item:is_defensive",
        "item:is_offensive",
        "item:already_held",      # we are carrying one of these already
    ],
    # The move tutor. It offers a replacement move for a specific team member,
    # and the engine can be asked what that member currently uses, with power
    # and type. Before this the agent saw two names and guessed: on seed 40003
    # it took SKIP over three offers scoring 68.6 / 65.6 / 68.6 / 70.4.
    "tutor": [
        "tutor:power_gain",       # offered power minus what they use now
        "tutor:is_upgrade",
        "tutor:on_lead",
        "tutor:on_strongest",
        "tutor:same_type",        # STAB: matches the recipient's own type
    ],
    "order": [
        "order:noop",              # the leave-it option itself
        "order:hp_gain",           # candidate HP frac minus the leader's
        "order:swap_when_lead_hurt",
        "order:cand_level_rel",
        "order:cand_is_strongest",
        "order:cand_new_type",     # covers a type the current leader does not
        "order:cand_fainted",      # promoting a corpse
    ],
}

ALL_GROUPS = list(GROUPS)


def feature_names(groups: list[str] | None = None) -> list[str]:
    """The vector's index order, named.

    Explicit names are most of the point of a linear model: a trained weight
    vector can be read and argued with. With no argument this is the full set,
    which must stay byte-identical to what shipped — `bots/sarsa-v2/bot.py` freezes a
    copy of it, and a test holds the two side by side.
    """
    for g in (groups or []):
        if g not in GROUPS:
            raise KeyError(f"unknown feature group '{g}' — have: {', '.join(ALL_GROUPS)}")
    chosen = ALL_GROUPS if groups is None else [g for g in ALL_GROUPS if g in groups]
    return [n for g in chosen for n in GROUPS[g]]


N_FEATURES = len(feature_names())


def features(state: dict[str, Any], action: dict[str, Any],
             index: dict[str, int] | None = None) -> dict[int, float]:
    """Sparse x(s, a): index -> value. Only non-zero entries.

    `index` is a name -> position map, so a variant with some groups switched off
    computes the same quantities and simply drops the ones it does not carry.
    The alternative — a separate function per variant — is how two feature sets
    silently stop meaning the same thing.
    """
    names = _NAME_INDEX if index is None else index
    x: dict[int, float] = {}

    def put(name: str, value: float = 1.0) -> None:
        # A name the variant left out is skipped, not an error: that is what
        # switching a group off means.
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
        # `b is None` is the leave-it option. Everything else brings slot b to
        # the front, so the features describe b relative to whoever leads now.
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
        # Which of the options on offer is objectively the beefiest.
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
            # On the swap screen the listed Pokemon is the one RELEASED, so
            # releasing the weakest is the good move and releasing the best is
            # the mistake. Same list, opposite meaning: see state["prompt"].
            if screen == "swap-screen":
                put("swap_out_weakest", 1.0 if idx == weakest else 0.0)
    return x


_NAME_INDEX = {n: i for i, n in enumerate(feature_names())}


class FeatureSet:
    """One variant of the vector: which groups are in, and their index order.

    Carrying the group list around with the weights is what keeps an ablation
    honest. Weights are saved by NAME, so loading them into a different set would
    otherwise zero-fill the missing ones and quietly produce a policy nobody
    trained.
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
    """The team-order decision, as a list of actions scored like any other.

    Always leads with the leave-it option, so "do nothing" competes on the same
    footing instead of being a special case in the caller. Empty when there is
    nothing to decide, which the caller reads as "skip this decision point".

    Only slot 0 is a target: what matters is who LEADS, and offering all fifteen
    pairs of a full team would spend the sample budget on distinctions that do
    not pay.
    """
    team = state.get("team") or []
    if not state.get("can_reorder") or len(team) < 2:
        return []
    return [{"kind": "reorder", "b": None}] + [
        {"kind": "reorder", "b": j} for j in range(1, len(team))
    ]


# Effect kinds, keyed on the item id, because the engine keeps no structured
# effect field: an item is {id, name, desc, icon} and the numbers live inline in
# the battle code. Only the COARSE kind is encoded here, never a magnitude — a
# magnitude table would have to be copied out of the bundle and would keep
# reporting the old value after any upstream rebalance, silently. See TODO.md.
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
    """Best available handle on which item a button is offering.

    The label is prose the engine wrote ("Choice Scarf +50% Speed"), so the name
    is turned into the id shape the engine itself uses. Not free of risk, but the
    only alternative is matching the description sentence, which is worse.
    """
    label = (action.get("label") or "").strip().lower()
    words = re.split(r"[^a-z]+", label)
    return "_".join(w for w in words[:2] if w)


def _item_features(put, state: dict[str, Any], action: dict[str, Any]) -> None:
    item = _item_id(action)
    team = state.get("team") or []
    type_items = state.get("type_items") or {}
    # TYPE_ITEM_MAP is Pokemon type -> item id, so invert it: this item boosts
    # this type. The single structured item fact the engine gives away.
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
    """Judge the offer instead of guessing at its name.

    The label carries the offered move and who receives it. What it does NOT
    carry is power or type — and the agent used to have no way to tell a 130-power
    upgrade from a sidegrade, which is how it learned to take SKIP. `move` on each
    team member is the engine's own answer for what they use now, so the offer can
    be compared against it.
    """
    team = state.get("team") or []
    if not team:
        return
    # "→ SURF:Wartortle Lv35" / "→ SURF — WARTORTLE LV35 • ..."
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


ARCH_VERSION = 1


class DrrnBot(Bot):
    """The same features as sarsa-v2, scored by a network instead of a dot product.

    The forward pass is written out in plain Python on purpose. The net is
    trained with numpy in `experiments/drrn/`, but a bot has to load in any
    checkout with the package's two dependencies installed — so what ships is a
    JSON of matrices and thirty lines of arithmetic, not a dependency.
    """

    name = "drrn"

    def __init__(self, seed: int = 0, weights: str | Path | None = None) -> None:
        path = Path(weights) if weights else find_weights()
        if not path.is_file():
            raise FileNotFoundError(
                f"no weights at {path}.\n"
                "They ship next to this file, so this usually means the folder was "
                "copied without its artifacts/.\n"
                "To play a different set:  POKELIKE_DRRN_WEIGHTS=/path/to/weights.json"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("encoding_version")
        if version != FEATURES_VERSION:
            raise ValueError(
                f"these weights were trained with feature set v{version}, and this "
                f"bot speaks v{FEATURES_VERSION}. The indices no longer point at the "
                f"same features, so they would be read as a different policy "
                f"entirely: retrain, or load them with a bot of the matching version."
            )
        if data.get("arch_version") != ARCH_VERSION:
            raise ValueError(
                f"these weights were written by architecture "
                f"v{data.get('arch_version')} and this bot is v{ARCH_VERSION}. A "
                f"matrix is only a policy under the shape that produced it."
            )
        # Transposed once, here: the forward pass walks columns, and doing it
        # per decision would repeat the same work a few hundred times a run.
        self.W = [[[float(v) for v in row] for row in layer] for layer in data["W"]]
        self.b = [[float(v) for v in layer] for layer in data["b"]]
        self.n_in = int(data["n_in"])
        self.weights_path = path
        self.trained_updates = data.get("transitions", 0)
        self.rng = random.Random(seed)
        self.decisions = 0
        self._last_why = ""

    def reset(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def q(self, x: dict[int, float]) -> float:
        """One forward pass. ReLU everywhere but the last layer, which is linear.

        The input is sparse — about nine of a hundred features are non-zero at
        any decision — so the first layer is computed from the non-zero entries
        rather than from a dense vector of mostly noughts.

        `len(self.W) > 1` is not defensive: with no hidden layer at all the first
        layer IS the last, and rectifying it would clamp every negative q-value
        to zero while the numpy side returned wᵀx. That net is the linear control
        arm — the same fitted Q iteration on the same data with the shape of q̂
        put back — so the arm that exists to isolate capacity is exactly the one
        the two implementations disagreed on.
        """
        h = list(self.b[0])
        W0 = self.W[0]
        for i, v in x.items():
            row = W0[i]
            for j in range(len(h)):
                h[j] += row[j] * v
        if len(self.W) > 1:
            h = [v if v > 0.0 else 0.0 for v in h]

        for layer in range(1, len(self.W)):
            W, b = self.W[layer], self.b[layer]
            nxt = list(b)
            for i, hi in enumerate(h):
                if hi == 0.0:
                    continue
                row = W[i]
                for j in range(len(nxt)):
                    nxt[j] += row[j] * hi
            h = nxt if layer == len(self.W) - 1 else [v if v > 0.0 else 0.0 for v in nxt]
        return h[0]

    def act(self, state: dict[str, Any]) -> int:
        """Greedy over q̂(s, a, w). Ties broken at random, seeded.

        There is no unseen-state fallback and none is needed: unlike a table,
        a linear model returns a value for every action it has never met, which
        is the reason for using one on a sample budget this small.
        """
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
        """Who should lead the next battle, scored by the same weights.

        Team order is a decision the game does not put in `state["actions"]`,
        because taking it costs no turn. It is trained as an extra state in the
        MDP with reward 0, so the very same q-hat ranks "leave it" against each
        candidate — no second model, no separate rule.
        """
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
        """Goes into the run registry and the benchmark result."""
        return {
            "weights": self.weights_path.name,
            "features_version": FEATURES_VERSION,
            "arch_version": ARCH_VERSION,
            "n_features": N_FEATURES,
            "hidden": [len(b) for b in self.b[:-1]],
            "trained_on_transitions": self.trained_updates,
            "decisions": self.decisions,
        }

    def artifacts(self) -> list:
        """What a submission of this bot must carry with it.

        The weights alone are not enough to understand a result: the feature
        version says what the numbers index, and without the training config the
        score is something nobody can reproduce or improve on.
        """
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
                    "algorithm": "fitted Q iteration, MLP on x(s,a)",
                    "features_version": FEATURES_VERSION,
                    "arch_version": ARCH_VERSION,
                    "n_features": N_FEATURES,
                    "hidden": stored.get("hidden"),
                    "hyperparameters": stored.get("hyperparameters"),
                    "transitions": stored.get("transitions"),
                    "episodes": stored.get("episodes"),
                    "trainer": "experiments/drrn/train.py",
                },
            ),
        ]
