"""The turn journal: what happened, what the model said, and how much to keep.

Building and trimming the per-turn record, and assembling the user message that
wraps it around the state view. The journal is what stops a bot walking the same
loop forever, and the "pick an index" line is what tells the model how many
options there are.
"""

from __future__ import annotations

from typing import Any


def journal_entry(state: dict[str, Any], index: int, why: str) -> str:
    """Builds one past-turn record from the action taken and the model's reason.

    In: the state dict at the moment of the decision, the chosen index, and the
    model's own sentence about it. Out: a formatted string with the game's record
    on the first line and the model's reasoning (labelled as such) beneath it.
    """
    # What was actually done comes from state["actions"][index], which is the
    # harness's own data, not the model's guess. The reasoning is worth keeping
    # (it is how a model notices it has been trying the same idea for five turns)
    # but it is not evidence. Separating them in the record is what lets a model
    # tell plan from fact.
    actions = state.get("actions") or []
    chosen = actions[index] if 0 <= index < len(actions) else {}
    if chosen.get("kind") == "node":
        did = f"node {chosen.get('id', '?')} ({chosen.get('node', 'node')})"
    else:
        did = str(chosen.get("label") or chosen.get("id") or "action")
    said = " ".join(str(why or "").split())[:200]
    return (f"step {state.get('steps')}: [{index}] {did}\n"
            f"    it said: {said or '(nothing)'}")


def trim_journal(journal: list[str], memory: int) -> list[str]:
    """Applies the memory cap to the journal list.

    In: the full journal and the memory setting (positive caps, negative keeps
    all). Out: the trimmed list (or the original if memory < 0).
    """
    # memory == -1 keeps every turn: an unbounded, append-only memory.
    if memory >= 0:
        return journal[-memory:]
    return journal


def build_user_message(
    state_view: str,
    journal: list[str],
    n_actions: int,
) -> str:
    """Assembles the full user message: view, journal, and instruction line.

    In: the rendered state view string, the journal list, and the number of legal
    actions. Out: the complete user-role message for the model.
    """
    # Deliberately not the hook for bots. The journal separates what was done from
    # what was said about it, and the heading says so. It used to read YOUR RECENT
    # MOVES over a list of the model's own sentences, which is the one arrangement
    # that turns a guess into a fact by doing nothing at all.
    parts = [state_view]
    if journal:
        parts += [
            "",
            "WHAT YOU DID, AND WHAT YOU SAID AT THE TIME.",
            "The action on each first line is the game's record. The sentence "
            "under it is your own from that turn: it is what you meant to do, "
            "not something that has been verified since.",
            *(f"  {r}" for r in journal),
        ]
    parts += [
        "",
        f"Pick an index between 0 and {n_actions - 1} and call play().",
    ]
    return "\n".join(parts)
