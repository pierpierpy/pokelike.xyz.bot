"""A policy learned by LSTD-Q(lambda) + Least-Squares Policy Iteration,
playing greedily.

    uv run pokelike bot run --bot lspi --seed 40003 --runs 1 -g -dd
    uv run pokelike bot bench --bot lspi --dry-run

    q̂(s, a, w) = wᵀ x(s, a)

Trained by `experiments/lspi/train.py` (research folder, not shipped — see
that experiment's README for the full derivation and measurements). Lagoudakis
& Parr, "Least-Squares Policy Iteration", JMLR 4 (2003); Boyan (2002) for the
lambda trace form of the policy-evaluation step this method's `w` is solved
from.

WHAT THIS IS, BRIEFLY
----------------------
Same 100 hand-built linear features, same environment, same reward as
`bots/sarsa-v2`. What differs is HOW `w` is estimated: LSTD-Q solves the exact
linear fixed point of the projected Bellman equation from batch statistics
accumulated over real transitions, then Least-Squares Policy Iteration
re-solves periodically as the policy improves and more data arrives — rather
than an incremental, step-size-driven update. Measured on the official
50-seed benchmark: 1.44 badges mean, best single run 8 badges, against
sarsa-v2's 1.36 and a freshly retrained copy of sarsa-v2's own algorithm at
1.32 in the same session. Three other ways of reusing real transitions harder
(replay, in three forms) were tried first and measured worse than plain
SARSA(λ) — see `experiments/rl_sample_efficient/README.md`.

WHY THE FEATURE CODE IS COPIED IN HERE
--------------------------------------
Same reasoning as `bots/sarsa-v2/bot.py` and every other bot in this project:
a submission must stand on its own, and the representation here is UNCHANGED
from `experiments/sarsa`'s — same 100 features, same encoding version, same
index order. This experiment's whole question is whether a different
estimator learns a better policy from the same real transitions, not whether
a different feature vector would.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from pokelike.bot.base import Bot

FEATURES_VERSION = 2

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "artifacts" / "weights.json"


def find_weights() -> Path:
    override = os.environ.get("POKELIKE_LSPI_WEIGHTS")
    return Path(override) if override else WEIGHTS


# ---------------------------------------------- the frozen feature set, v2
#
# Byte-identical to experiments/sarsa/features/groups.py. Not imported, for
# the reason above.

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


GROUPS: dict[str, list[str]] = {
    "context": ["bias", "team_size", "min_hp", "mean_hp", "map_index", "depth",
                "badges", "any_fainted", "n_actions"],
    "node": [f"node:{k}" for k in NODE_KINDS],
    "node_deep": [f"node:{k}*deep" for k in NODE_KINDS],
    "node_hurt": [f"node:{k}*hurt" for k in NODE_KINDS],
    "node_team": [f"node:{k}*small_team" for k in NODE_KINDS],
    "lookahead": ["leads_to_heal", "leads_to_catch", "leads_to_boss", "leads_dead_end"],
    "screen": [f"screen:{s}" for s in SCREENS],
    "mon": ["mon_new_type", "mon_level_rel", "mon_power", "mon_bulk", "mon_atk",
            "mon_shiny", "mon_best_stats"],
    "slot": ["equip_on_strongest", "equip_on_weakest", "swap_out_weakest"],
    "button": ["is_skip", "is_cancel", "is_bag"],
    "item": [
        "item:matches_my_type",
        "item:matches_lead_type",
        "item:is_evolution",
        "item:is_healing",
        "item:is_defensive",
        "item:is_offensive",
        "item:already_held",
    ],
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
    for g in (groups or []):
        if g not in GROUPS:
            raise KeyError(f"unknown feature group '{g}' — have: {', '.join(ALL_GROUPS)}")
    chosen = ALL_GROUPS if groups is None else [g for g in ALL_GROUPS if g in groups]
    return [n for g in chosen for n in GROUPS[g]]


N_FEATURES = len(feature_names())


def features(state: dict[str, Any], action: dict[str, Any],
             index: dict[str, int] | None = None) -> dict[int, float]:
    names = _NAME_INDEX if index is None else index
    x: dict[int, float] = {}

    def put(name: str, value: float = 1.0) -> None:
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
        rivals = [parse_pokemon(o.get("label") or "") for o in state["actions"]]
        totals = [r["hp"] + r["atk"] + r["def"] for r in rivals]
        mine = mon["hp"] + mon["atk"] + mon["def"]
        put("mon_best_stats", 1.0 if totals and mine >= max(totals) else 0.0)
        return x

    if screen in ("item-equip-modal", "swap-screen") and team:
        idx = action.get("idx", 0)
        if idx < len(team):
            atk_of = [p.get("base_stats", {}).get("atk", 0) for p in team]
            hp_of = [p["hp"] for p in team]
            strongest = max(range(len(team)), key=lambda i: atk_of[i])
            weakest = min(range(len(team)), key=lambda i: (team[i]["level"], hp_of[i]))
            put("equip_on_strongest", 1.0 if idx == strongest else 0.0)
            put("equip_on_weakest", 1.0 if idx == weakest else 0.0)
            if screen == "swap-screen":
                put("swap_out_weakest", 1.0 if idx == weakest else 0.0)
    return x


_NAME_INDEX = {n: i for i, n in enumerate(feature_names())}


def reorder_options(state: dict[str, Any]) -> list[dict[str, Any]]:
    team = state.get("team") or []
    if not state.get("can_reorder") or len(team) < 2:
        return []
    return [{"kind": "reorder", "b": None}] + [
        {"kind": "reorder", "b": j} for j in range(1, len(team))
    ]


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
    label = (action.get("label") or "").strip().lower()
    words = re.split(r"[^a-z]+", label)
    return "_".join(w for w in words[:2] if w)


def _item_features(put, state: dict[str, Any], action: dict[str, Any]) -> None:
    item = _item_id(action)
    team = state.get("team") or []
    type_items = state.get("type_items") or {}
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


class LSPIBot(Bot):
    name = "lspi"

    def __init__(self, seed: int = 0, weights: str | Path | None = None) -> None:
        path = Path(weights) if weights else find_weights()
        if not path.is_file():
            raise FileNotFoundError(
                f"no weights at {path}.\n"
                "They ship next to this file, so this usually means the folder was "
                "copied without its artifacts/.\n"
                "To play a different set:  POKELIKE_LSPI_WEIGHTS=/path/to/weights.json"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("encoding_version")
        if version != FEATURES_VERSION:
            raise ValueError(
                f"these weights were trained with feature set v{version}, and this "
                f"bot speaks v{FEATURES_VERSION}: retrain, or load a matching version."
            )
        stored = data.get("weights") or {}
        self.w = [float(stored.get(n, 0.0)) for n in feature_names()]
        self.weights_path = path
        self.n_folded = data.get("n_folded", 0)
        self.rng = random.Random(seed)
        self.decisions = 0
        self._last_why = ""

    def reset(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def q(self, x: dict[int, float]) -> float:
        return sum(self.w[i] * v for i, v in x.items())

    def act(self, state: dict[str, Any]) -> int:
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
        return {
            "weights": self.weights_path.name,
            "features_version": FEATURES_VERSION,
            "n_features": N_FEATURES,
            "n_folded": self.n_folded,
            "decisions": self.decisions,
        }

    def top_weights(self, n: int = 12) -> list[tuple[str, float]]:
        pairs = sorted(zip(feature_names(), self.w), key=lambda p: -abs(p[1]))
        return [(name, round(w, 3)) for name, w in pairs[:n]]

    def artifacts(self) -> list:
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
                    "algorithm": "LSTD-Q(lambda) + least-squares policy iteration "
                                 "(Lagoudakis & Parr 2003; Boyan 2002)",
                    "features_version": FEATURES_VERSION,
                    "n_features": N_FEATURES,
                    "hyperparameters": stored.get("hyperparameters"),
                    "n_folded": stored.get("n_folded"),
                    "trainer": "experiments/lspi/train.py",
                    "top_weights": dict(self.top_weights(15)),
                },
            ),
        ]
