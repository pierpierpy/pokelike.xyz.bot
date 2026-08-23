"""Turning (state, action) into a feature vector.

This is the part that matters. Tabular Dyna-Q is blind by construction because it
compresses the state to six numbers and keys actions by type, so on the starter
screen it learns Q values of 6.3, 6.2, 6.3, three indistinguishable slots where
a player sees Bulbasaur, Charmander and Squirtle. No amount of extra episodes
fixes that, because the information never reaches the table.

Linear function approximation (Sutton & Barto, chapter 9) lets us hand the agent
what it was missing:

    q̂(s, a, w) = wᵀ x(s, a)

Two consequences beyond seeing more. Features generalise, so a lesson learned
about "catching something that adds a type I lack" transfers to every such
choice rather than to one table cell, which matters enormously here, because
every real step costs 0.7 seconds of browser. And actions are described rather
than named, so five equip buttons are five different vectors instead of one
collapsed key.

The features are deliberately hand-made and few. With ~15 s per episode there is
no budget for learning a representation from scratch, so the domain knowledge
goes in by hand and the agent learns the weights.
"""

from __future__ import annotations

import re
from typing import Any

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
# rest keep their meaning. The group order is the index order and must not be
# reshuffled, because a weight vector is a plain list, and `w[43]` means
# `mon_new_type` only because this list says so.
#
# The groups exist because of what the first trained policy turned out to look
# like. Its heaviest weights were all in `context`, features that depend on the
# state but not on the action, so they shift every option by the same amount and
# cancel in the argmax. They fit the level of the return, not the choice. That is
# a hypothesis you can only test by taking them away, which is what this is for.
GROUPS: dict[str, list[str]] = {
    # State only. These features cannot discriminate between actions, by construction.
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
    # Identifies which screen the choice is on. Also state only.
    "screen": [f"screen:{s}" for s in SCREENS],
    # What is actually on the card, the part the tabular agent could not see.
    "mon": ["mon_new_type", "mon_level_rel", "mon_power", "mon_bulk", "mon_atk",
            "mon_shiny", "mon_best_stats"],
    # Which team member a slot-shaped screen is pointing at.
    "slot": ["equip_on_strongest", "equip_on_weakest", "swap_out_weakest"],
    "button": ["is_skip", "is_cancel", "is_bag"],
    # Team order. A separate decision that is not one of the game's actions.
    # Slot 0 leads the next battle but reordering does not consume the turn. The
    # options are "leave it" plus "bring slot j to the front".
    #
    # Every feature here is written as a difference against the current leader,
    # or as an interaction with `noop`. A feature that reads the same for the
    # leave-it option and for every swap would add the same number to all of
    # them and cancel in the argmax, which is exactly the mistake the ablation
    # was built to catch.
    # Items. Before these were added, the item screen produced three identical
    # q-values because the agent was choosing at random among a Red Card, a
    # Moon Stone and an Assault Vest.
    #
    # Item effects are not structured data anywhere. An item is {id, name, desc,
    # icon} and every magnitude is inline in the battle code, keyed on the
    # string id. So these features read the two things that are structured: the
    # id, and TYPE_ITEM_MAP, the engine's own type-to-item table, which collapses
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
    # and type. Before these features were added, the agent saw two names and
    # guessed. On seed 40003 the agent took SKIP over three offers scoring
    # 68.6 / 65.6 / 68.6 / 70.4.
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

    Explicit names are most of the point of a linear model, because a trained
    weight vector can be read and argued with. With no argument this returns the
    full set, which must stay byte-identical to what shipped. The file
    `bots/sarsa-v2/bot.py` freezes a copy of it, and a test holds the two side
    by side.
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

    The `index` parameter is a name-to-position map, so a variant with some
    groups switched off computes the same quantities and simply drops the ones it
    does not carry. The alternative, a separate function per variant, is how two
    feature sets silently stop meaning the same thing.
    """
    names = _NAME_INDEX if index is None else index
    x: dict[int, float] = {}

    def put(name: str, value: float = 1.0) -> None:
        # A name the variant left out is skipped rather than treated as an error, because that is what
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
            # On the swap screen the listed Pokemon is the one released, so
            # releasing the weakest is the good move and releasing the best is
            # the mistake. The same list has the opposite meaning (see state["prompt"]).
            if screen == "swap-screen":
                put("swap_out_weakest", 1.0 if idx == weakest else 0.0)
    return x


_NAME_INDEX = {n: i for i, n in enumerate(feature_names())}


class FeatureSet:
    """One variant of the vector, specifying which groups are in and their index order.

    Carrying the group list around with the weights is what keeps an ablation
    honest. Weights are saved by name, so loading them into a different set would
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

    The list always leads with the leave-it option, so "do nothing" competes on
    the same footing instead of being a special case in the caller. The list is
    empty when there is nothing to decide, which the caller reads as "skip this
    decision point".

    Only slot 0 is a target, because what matters is who leads, and offering all
    fifteen pairs of a full team would spend the sample budget on distinctions
    that do not pay.
    """
    team = state.get("team") or []
    if not state.get("can_reorder") or len(team) < 2:
        return []
    return [{"kind": "reorder", "b": None}] + [
        {"kind": "reorder", "b": j} for j in range(1, len(team))
    ]


# Effect kinds, keyed on the item id, because the engine keeps no structured
# effect field. An item is {id, name, desc, icon} and the numbers live inline in
# the battle code. Only the coarse kind is encoded here, never a magnitude,
# because a magnitude table would have to be copied out of the bundle and would
# keep reporting the old value after any upstream rebalance, silently.
# See TODO.md.
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
    # TYPE_ITEM_MAP is Pokemon type -> item id, so the inverted mapping shows which item boosts
    # which type. The single structured item fact the engine gives away.
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

    The label carries the offered move and who receives the move. The label does
    not carry power or type, and without those the agent had no way to tell a
    130-power upgrade from a sidegrade, which is how the agent learned to take
    SKIP. The `move` field on each team member is the engine's own answer for
    what the member currently uses, so the offer can be compared against the
    current move.
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
