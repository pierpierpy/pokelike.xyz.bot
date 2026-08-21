"""Tool declarations and shared game rules for the LLM harness.

The rules are shared, the strategy is not. The split matters: everything below
is a FACT about the game, several of them read out of the bundle rather than
guessed, and a benchmark where each bot restates the facts measures who copied
them correctly instead of who plays better.

The two that are easy to get wrong, and were:

  * BADGES ARE THE GOAL. The engine's score formula was written for the Battle
    Tower and two of its six terms never fire in Story mode, so a prompt that
    chases "maps cleared" points the model at something that is always zero.
    An earlier version of this prompt did exactly that.
  * Choosing a node CLOSES the others on that layer, forever.
"""

from __future__ import annotations

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
# Shared by default for the same reason the rules are: a model given a tool
# another model was not is not being compared, it is being helped.
#
# A bot may still add its own, or replace these outright -- see `tools()` and
# `answer_tool()` on LLMBot. What it may not do is hide that it did: the tool
# names go into every result and a bot whose set differs from the shared one is
# marked in the standings, so its row is read as the different question it is.

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
