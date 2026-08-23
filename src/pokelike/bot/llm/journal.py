"""The turn journal tracks what happened, what the model said, and how much to keep.

This module builds per-turn records and assembles the user message that wraps
them around the state view.
"""

from __future__ import annotations

from typing import Any


def journal_entry(state: dict[str, Any], index: int, why: str) -> str:
    """Builds one past-turn record from the action taken and the model's reason."""
    # The action comes from state["actions"][index], which is harness data.
    # The reasoning is kept so the model can notice repeated patterns, and it
    # is labelled as the model's own claim.
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

    A negative memory value keeps every turn; a positive value keeps the last N.
    """
    # memory == -1 keeps every turn.
    if memory >= 0:
        return journal[-memory:]
    return journal


def build_user_message(
    state_view: str,
    journal: list[str],
    n_actions: int,
    *,
    notes_block: list[str] | None = None,
    plan_block: list[str] | None = None,
) -> str:
    """Assembles the full user message from the view, notes, plan, journal, and
    instruction."""
    # Notes and plan come before the journal because cross-run learning
    # outranks recent turn history.
    parts = [state_view]
    if notes_block:
        parts += notes_block
    if plan_block:
        parts += plan_block
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
