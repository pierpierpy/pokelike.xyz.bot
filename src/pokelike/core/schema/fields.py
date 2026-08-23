"""The reference dictionaries describing every field a bot receives.

In: nothing (pure data). Out: importable dicts keyed by field name.
"""

from __future__ import annotations

# What each field means. Anything present in a real observation but missing from
# here is reported as undocumented when the schema is printed.
FIELDS = {
    "screen": "which screen you are on: map-screen, catch-screen, item-equip-modal, ...",
    "prompt": "what the screen is ASKING. Read it: on the swap screen the same "
              "list of your team means 'choose one to release', not 'choose a lead'",
    "layer": "'screen' or 'modal'. Modals are choices too, not decoration",
    "steps": "how many decisions this run has taken",
    "seed": "the run's seed; the same seed replays the same run",
    "region": ("which of the four story regions this run is in: kanto, johto, hoenn "
               "or sinnoh. Each has its own eight gyms, its own starters and its own "
               "Elite Four, and a run plays exactly one of them"),
    "done": "True when the run is over",
    "run": "run-wide facts: map index, badges, whether anyone has fainted",
    "team": "your Pokemon, in order. Everything about them",
    "bag": "item names you are carrying",
    "map": "the whole board: nodes, edges, where you stand",
    "stats": "the engine's cumulative counters, updated after every battle",
    "actions": "THE LEGAL MOVES. act() returns an index into this list",
    "bag_items": ("the bag with ids: [{id, name, desc, usable}]. `bag` is the same "
                  "list as bare names. The id is the handle that matters, because item "
                  "effects are not structured anywhere in the engine, so the id is "
                  "what every effect in the battle code is keyed on"),
    "offered_moves": ("what the move tutor WOULD offer each team member, by index: "
                      "{name, power, type, special}. Computed with the engine's own "
                      "getBestMove, the same call it builds the tutor button from, "
                      "so the offer can be compared against `team[i].move` instead of "
                      "guessed at from a name"),
    "type_items": ("the engine's type -> held-item table, 18 entries "
                   "(Fire -> charcoal). Collapses eighteen nearly identical "
                   "'+40% X-type damage' items into one question: does this boost a "
                   "type I actually field"),
    "can_reorder": ("whether the team can be reordered right now. Slot 0 leads the "
                    "next battle, so the order is a decision, but a FREE one, which "
                    "is why it is not in `actions`: see Bot.reorder / Game.reorder"),
    "stalled": "only present if the engine stopped responding (should never happen)",
}

RUN_FIELDS = {
    "badges": "gym badges earned. This is the progression metric in Story mode",
    "map": "which map you are on, 0-indexed",
    "run_seed": "the engine's internal seed for this run",
    "max_team_size": "high-water mark of team size, NOT a limit (the limit is 6)",
    "anyone_fainted": "whether anything has fainted this run",
    "items_this_run": "items picked up",
    "elite": "Elite Four progress",
    "nuzlocke": "whether nuzlocke rules are on",
    "finished": "engine's own end-of-run flag",
}

TEAM_FIELDS = {
    "name": "species name, e.g. 'Bulbasaur'",
    "species_id": "national dex number",
    "level": "current level",
    "hp": "current HP",
    "max_hp": "maximum HP. hp/max_hp is what tells you if it is in danger",
    "types": "list of types, e.g. ['Grass', 'Poison']. This decides battles",
    "base_stats": "hp, atk, def, speed, special, spdef",
    "item_id": ("the held item's id, e.g. 'leftovers'. The name is for reading, the "
                "id is for deciding: every effect in the battle code is keyed on it"),
    "item_desc": "the held item's effect, as the English sentence the engine wrote",
    "move": ("what this Pokemon attacks with: {name, power, type, special}, from the "
             "engine's own getMoveForPokemon. Not derivable from anything on screen"),
    "item": "held item name, or null",
    "shiny": "whether it is shiny (worth points at the end)",
    "move_tier": "which tier of moves it knows",
    "mega_stone": "held mega stone, or null",
    "uid": "unique id within the run",
}

MAP_FIELDS = {
    "nodes": ("every node: id, kind, layer, col, accessible, visited, revealed, "
              "and `tooltip`, the text the game itself shows when a person rests the "
              "pointer on it. That is where the detail lives: a trainer's archetype "
              "and the types they use, a gym leader's roster with levels, what a trade "
              "does. None of it is anywhere else in the state"),
    "edges": "[from, to] pairs. This is how you know where a choice leads",
    "current": "id of the node you are standing on",
}

NODE_KINDS = {
    "start": "where the map begins",
    "catch": "adds a Pokemon to your team",
    "battle": "one wild Pokemon",
    "trainer": "1 Pokemon on map 0, 2 on maps 1-2, 3 from map 3 onwards",
    "item_id": ("the held item's id, e.g. 'leftovers'. The name is for reading, the "
                "id is for deciding: every effect in the battle code is keyed on it"),
    "item_desc": "the held item's effect, as the English sentence the engine wrote",
    "move": ("what this Pokemon attacks with: {name, power, type, special}, from the "
             "engine's own getMoveForPokemon. Not derivable from anything on screen"),
    "item": "pick one of three items",
    "pokecenter": "restores HP",
    "question": "unknown until you enter it (shown as `unknown` in logs)",
    "boss": "the gym leader at the bottom of the map",
    "trade": "trade a Pokemon",
    "move_tutor": "teach a move",
    "pokemart": "buy something",
    "shiny": "a shiny encounter",
}
