"""This module provides tool declarations and shared game rules for the LLM harness.

The rules are shared across all LLM bots because they are facts about the game.
A benchmark where each bot restates them would measure who copied them correctly
rather than who plays better.
"""

from __future__ import annotations

from typing import Any

from .config import LLMConfigError

# ---------------------------------------------------------------- what is true

GAME_RULES = """You are playing Pokelike, a Pokemon roguelike.

YOUR GOAL: earn as many gym badges as you can before your team is wiped out.
Badges measure how far you got. A run ends when every Pokemon has fainted.

HOW A TURN WORKS
- The map is a layered graph running top to bottom, with a boss at the bottom.
- You pick one node from the legal ones. The moment you pick, every other node on
  that layer CLOSES FOREVER. The choice is irreversible and it also decides which
  nodes you will be able to reach next.
- Battles resolve themselves. You never choose moves. What you decide is where to
  go, who to catch, which item to take and who to give it to.
- Your team holds up to 6 Pokemon.

NODE TYPES
  o catch        adds a Pokemon to your team
  x wild fight   one wild Pokemon, gives experience
  T trainer      1 Pokemon on map 0, 2 on maps 1-2, 3 from map 3 onwards
  i item         an item to equip or keep
  + pokecenter   restores HP
  ? unknown      only revealed when you enter it
  $ trade        M move tutor    S shop    B boss

WHAT ACTUALLY KILLS RUNS
Losing Pokemon. Every faint is permanent for that run, and once the team is empty
it is over, no matter how well you were doing.
"""

CLOSING = "\nThink briefly, then call `play` with your chosen index. Always call `play`."


# ---------------------------------------------------------------------- tools
#
# These tools are shared by default. A bot may add its own or replace these
# through `tools()` and `answer_tool()` on LLMBot. The tool names go into every
# result, and a bot whose set differs from the shared one is marked in the
# standings.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "team_details",
            "description": "Full team stats: HP, levels, types, held items.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "what_lies_ahead",
            "description": (
                "For each legal action, which nodes it leads to on the next layer. "
                "Useful to avoid closing off good paths: this choice decides what "
                "you will be able to do next."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_lead",
            "description": (
                "Move a team member to slot 0, so they enter the next battle first. "
                "Free: it does not use the turn, and you still have to call play "
                "afterwards. Only offered on the map screen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "team slot to promote"},
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play",
            "description": "Perform the chosen action and end the turn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "index of the legal action"},
                    "why": {"type": "string", "description": "one sentence on the reason"},
                },
                "required": ["index", "why"],
            },
        },
    },
]


_STOCK_TOOL_NAMES = [t["function"]["name"] for t in TOOLS]


# ----------------------------------------------------------------- opt-in tools
#
# These tools are not in the default TOOLS list. They are added only when the
# config enables them: notes_cap > 0 adds the three memory tools, plan_chars > 0
# adds the plan tool, and bag_tool adds the bag tool.

def remember_tool(note_chars: int) -> dict[str, Any]:
    """Returns the `remember` tool, telling the model the budget a note really has.

    The budget is stated because it is enforced: `Notebook.remember` truncates at
    the same number. Left unsaid, a bot author who raises `note_chars` changes
    nothing, since the model has no way to know it has more room and keeps writing
    a single line.

    One note still holds one idea, which is what makes a note possible to revise or
    drop later on its own, whatever length it runs to.
    """
    return {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Write down something you have learned about this game, to be shown "
                "back to you on every later turn AND in later runs. Use it for "
                "lessons that will still be true next time, not for what is on "
                f"screen now. One note holds one idea, and you have up to "
                f"{note_chars} characters for it, so say as much as the idea needs. "
                "Anything past that is cut off."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string",
                             "description": f"one lesson, up to {note_chars} characters"},
                },
                "required": ["note"],
            },
        },
    }


REVISE_TOOL = {
    "type": "function",
    "function": {
        "name": "revise",
        "description": (
            "Replace one of your notes with a better version of it. Use this "
            "when a lesson turns out to be half right: your notes are capped, "
            "so sharpening one is often worth more than adding another."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "which note, as numbered"},
                "note": {"type": "string", "description": "what it should say instead"},
            },
            "required": ["id", "note"],
        },
    },
}

FORGET_TOOL = {
    "type": "function",
    "function": {
        "name": "forget",
        "description": (
            "Delete one of your notes. Worth doing when a lesson was wrong, or "
            "when you need the room for a better one."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "which note, as numbered"},
            },
            "required": ["id"],
        },
    },
}


def plan_tool(plan_chars: int) -> dict[str, Any]:
    """Returns the `plan` tool, telling the model the budget a route really has.

    The same reasoning as `remember_tool`: the route is truncated at `plan_chars`,
    so saying the number is what lets a raised budget change anything.
    """
    return {
        "type": "function",
        "function": {
            "name": "plan",
            "description": (
                "Write down the route you mean to take through this map, and why. "
                "It is shown back to you every turn until you change it, so it is "
                "how a decision made now reaches the turn that has to honour it. "
                "Calling this again replaces it. Choosing a node closes every other "
                "node on that layer forever, so the order you take them in is most "
                f"of the game. You have up to {plan_chars} characters, and anything "
                "past that is cut off."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": f"the plan, up to {plan_chars} characters",
                    },
                },
                "required": ["route"],
            },
        },
    }

BAG_TOOL = {
    "type": "function",
    "function": {
        "name": "bag",
        "description": "What you are carrying: items in your bag.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def notebook_tools(note_chars: int) -> list[dict[str, Any]]:
    """Returns the three memory tools, with the note budget stated in the first."""
    return [remember_tool(note_chars), REVISE_TOOL, FORGET_TOOL]


def build_tools(
    *,
    notes_cap: int = 0,
    note_chars: int = 160,
    plan_chars: int = 0,
    bag_tool: bool = False,
    extra_tools: list[dict[str, Any]] | None = None,
    decorated_tools: list[dict[str, Any]] | None = None,
    drop_tools: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Assembles the full tool list from the config flags, deduplicating by name.

    When two tools share a name, precedence is decorated over extra_tools over shared.
    """
    result = list(TOOLS)
    if notes_cap > 0:
        result.extend(notebook_tools(note_chars))
    if plan_chars > 0:
        result.append(plan_tool(plan_chars))
    if bag_tool:
        result.append(BAG_TOOL)
    if extra_tools:
        result.extend(extra_tools)
    if decorated_tools:
        result.extend(decorated_tools)
    # Deduplication keeps the last occurrence of each name (highest precedence).
    seen: dict[str, int] = {}
    for i, t in enumerate(result):
        seen[t["function"]["name"]] = i
    kept = [result[i] for i in sorted(seen.values())]
    # The loop relies on `play` by name and reads `index`/`why` from it.
    for t in (list(extra_tools or []) + list(decorated_tools or [])):
        if t["function"]["name"] == "play":
            raise LLMConfigError(
                "play cannot be redeclared: the loop ends the turn on it and reads "
                "`index` and `why` from its arguments. Name your tool something else.")
    if drop_tools:
        kept = [t for t in kept if t["function"]["name"] not in drop_tools]
    return kept
