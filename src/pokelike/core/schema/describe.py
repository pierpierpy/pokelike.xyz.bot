"""Generates a human-readable schema description from a live observation.

In: a dict observation from the game. Out: formatted text (plain or markdown).

The self-check that reports undocumented fields runs every time the reference is
printed, so `pokelike schema` can never describe a game that no longer exists.
"""

from __future__ import annotations

import json
from typing import Any

from .fields import FIELDS, MAP_FIELDS, NODE_KINDS, RUN_FIELDS, TEAM_FIELDS


def describe(obs: dict[str, Any]) -> str:
    """The human-readable reference, built from a real observation.

    In: a mid-run observation dict. Out: the full formatted schema text.
    """
    out: list[str] = []
    add = out.append

    add("=" * 78)
    add("  WHAT A BOT RECEIVES")
    add("=" * 78)
    add("")
    add("  act(state) -> int         returns an index into state['actions']")
    add("")
    add("  One state, not a history. The history that matters is already inside:")
    add("  every node carries `visited`, and `stats` are cumulative from the start")
    add("  of the run.")
    add("")

    add("-" * 78)
    add("TOP LEVEL")
    add("-" * 78)
    for k in sorted(obs):
        doc = FIELDS.get(k, "*** UNDOCUMENTED, add it to schema.py ***")
        add(f"  {k:<12} {doc}")

    add("")
    add("-" * 78)
    add("state['actions']  ..  THE ONLY THING YOU MUST UNDERSTAND")
    add("-" * 78)
    add("  Between 2 and 7 entries. They change every turn, and they are NOT stable")
    add("  by position: index 2 is a battle now and a catch next turn.")
    add("")
    add("  Two shapes:")
    add("")
    add("  a map move                      any other choice")
    add("    kind:    'node'                 kind:  'element'")
    add("    id:      'n3_1'                 idx:   2")
    add("    node:    'catch'                label: 'Squirtle Lv. 5 WATER ...'")
    add("    layer:   3                      layer: 'catch-screen'")
    add("    col:     1")
    add("    tooltip: 'Catch Pokemon'")
    add("")
    add("  `tooltip` is what the game says this node IS, the same text it shows a")
    add("  person hovering over it. Read it: 'Officer \u2014 +2 Levels \u2014 "
        "Fire Pokemon'")
    add("  is the difference between a fight you win and one you do not.")
    add("")
    for a in (obs.get("actions") or [])[:3]:
        add(f"  real: {json.dumps(a)}")

    add("")
    add("  node kinds you will meet:")
    for k, v in NODE_KINDS.items():
        add(f"    {k:<12} {v}")

    add("")
    add("-" * 78)
    add("state['run']")
    add("-" * 78)
    for k in sorted(obs.get("run") or {}):
        add(f"  {k:<16} {RUN_FIELDS.get(k, '*** UNDOCUMENTED ***')}")

    add("")
    add("-" * 78)
    add("state['team'][i]")
    add("-" * 78)
    team = obs.get("team") or []
    for k in sorted(team[0]) if team else []:
        add(f"  {k:<14} {TEAM_FIELDS.get(k, '*** UNDOCUMENTED ***')}")

    add("")
    add("-" * 78)
    add("state['map']")
    add("-" * 78)
    for k in sorted(obs.get("map") or {}):
        add(f"  {k:<10} {MAP_FIELDS.get(k, '*** UNDOCUMENTED ***')}")
    add("")
    add("  Picking a node CLOSES every other node on that layer, forever. Use")
    add("  `edges` to see where a choice leads before taking it.")

    add("")
    add("-" * 78)
    add("state['stats']  ..  the engine's own counters, for building a reward")
    add("-" * 78)
    for k in sorted(obs.get("stats") or {}):
        add(f"    {k}")
    add("")
    add("  Cumulative and updated after every battle, so a per-step reward is the")
    add("  difference between two consecutive observations.")

    add("")
    add("-" * 78)
    add("WHAT IS NOT IN HERE")
    add("-" * 78)
    add("  * which item you were offered and refused on a node you skipped")
    add("  * what a '?' node will turn into, before you enter it")
    add("  * the enemy team, before the battle starts")
    add("  A human player does not know these either.")
    add("")
    add("  Also absent on purpose: any reward. Reward is a training signal, and it")
    add("  belongs to whatever is learning, not to the state. See")
    add("  experiments/env/rewards.py.")
    return "\n".join(out)


def as_markdown(obs: dict[str, Any]) -> str:
    """Wraps the schema description in markdown for STATE.md.

    In: a mid-run observation dict. Out: markdown text with code blocks.
    """
    # Headings start at h3: this is written into a section of STATE.md, not into
    # a file of its own, so an h1 or h2 here would break the document around it.
    return (
        "_Generated from a live observation. Edit `schema.py`, never this block._\n"
        "_Regenerate with `pokelike schema --markdown` after any change to_\n"
        "_`core/bridge.js`._\n\n"
        "```\n" + describe(obs) + "\n```\n\n"
        "### A real observation\n\n"
        "Trimmed where a list is long, never mid-structure, so it is still valid\n"
        "JSON you can paste somewhere and read.\n\n"
        "```json\n" + json.dumps(_trimmed(obs), indent=1) + "\n```\n"
    )


def _trimmed(obs: dict[str, Any], keep: int = 4) -> dict[str, Any]:
    """A shortened observation that is still valid JSON.

    In: a full observation and a max-items-per-list count. Out: the same dict
    with long lists truncated and a marker saying what was dropped.

    The previous version sliced the serialised text at 4000 characters, which cut
    through the middle of a map node and left the block unparseable, a reference
    sample nobody could paste anywhere. Long lists are shortened instead, with a
    marker saying what was dropped, so every KEY a bot can read is still present
    and the shape is intact.
    """
    def cut(seq: list, what: str) -> list:
        if len(seq) <= keep:
            return seq
        return [*seq[:keep], f"... {len(seq) - keep} more {what}"]

    out = dict(obs)
    if isinstance(out.get("map"), dict):
        m = dict(out["map"])
        m["nodes"] = cut(m.get("nodes") or [], "nodes")
        m["edges"] = cut(m.get("edges") or [], "edges")
        out["map"] = m
    for key, what in (("team", "team members"), ("bag", "items"),
                      ("bag_items", "items"), ("actions", "actions")):
        if isinstance(out.get(key), list):
            out[key] = cut(out[key], what)
    return out


def capture(game, seed: int = 42, max_steps: int = 12) -> dict[str, Any]:
    """A mid-run observation deep enough to show everything.

    In: a Game instance and optional seed/max_steps. Out: an observation dict
    with map, team and stats populated.

    A fresh run has no map and no team, and `stats` only appears after the first
    battle, which is exactly the field a bot author needs to build a reward. So
    we play on until the state has all three.
    """
    obs = game.reset(seed=seed)
    for _ in range(max_steps):
        if obs.get("done") or not obs.get("actions"):
            break
        if obs.get("map") and obs.get("team") and obs.get("stats"):
            break
        obs = game.step(0)
    return obs
