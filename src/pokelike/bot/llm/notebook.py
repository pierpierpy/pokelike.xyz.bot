"""The notebook provides remember, revise, and forget operations.

A capped list of notes the model writes for itself and sees every turn. Notes
survive across runs when cross_run_memory is on.
"""

from __future__ import annotations

from typing import Any


class Notebook:
    """A capped, numbered list of notes the model manages through tool calls."""

    def __init__(self, cap: int, note_chars: int) -> None:
        self.cap = cap
        self.note_chars = note_chars
        self.notes: list[str] = []
        # Every tool call recorded here, drained by the caller between decisions.
        self.tool_log: list[dict[str, Any]] = []

    def clear(self) -> None:
        """Wipes all notes (used on reset when cross_run_memory is off)."""
        self.notes = []

    def handle(self, verb: str, args: dict[str, Any]) -> str:
        """Dispatches one memory verb (remember/revise/forget) and returns the answer."""
        # Every answer states how full the notebook is, so the model knows
        # when to use revise/forget instead of remember.
        note = str(args.get("note") or "").strip().replace("\n", " ")
        note = note[: self.note_chars]

        if verb == "remember":
            return self._remember(note)
        if verb == "revise":
            return self._revise(args, note)
        if verb == "forget":
            return self._forget(args)
        return f"unknown notebook verb: {verb}"

    def view_block(self) -> list[str]:
        """Returns the notes as numbered lines for insertion into the user message."""
        if not self.notes:
            return ["", "WHAT YOU HAVE LEARNED SO FAR: nothing yet. Use `remember` "
                    "when you learn something that will still be true next run."]
        return ["", f"WHAT YOU HAVE LEARNED (kept across runs, "
                    f"{len(self.notes)}/{self.cap}):",
                *(f"  [{i}] {n}" for i, n in enumerate(self.notes, 1))]

    # ---------------------------------------------------------------- verbs

    def _remember(self, note: str) -> str:
        if not note:
            self._refused("empty note")
            return "nothing to remember: `note` was empty."
        if len(self.notes) >= self.cap:
            self._refused("notes full")
            return (f"your notes are full ({self.cap}). Use `revise` to "
                    f"improve one or `forget` to make room, then try again.")
        self.notes.append(note)
        self._kept()
        return (f"noted as [{len(self.notes)}]. "
                f"{len(self.notes)}/{self.cap} notes used.")

    def _revise(self, args: dict[str, Any], note: str) -> str:
        idx = self._parse_id(args)
        if idx is None:
            self._refused("no id")
            return (f"`id` must be a number between 1 and {len(self.notes)}."
                    if self.notes else "`id` must be a number (you have no notes).")
        if not 1 <= idx <= len(self.notes):
            self._refused("no such note")
            return (f"there is no note [{idx}]. You have {len(self.notes)}: "
                    f"use a number between 1 and {len(self.notes)}.")
        if not note:
            self._refused("empty note")
            return "nothing to revise it to: `note` was empty."
        was = self.notes[idx - 1]
        self.notes[idx - 1] = note
        self._kept(was=was)
        return (f"note [{idx}] rewritten. "
                f"{len(self.notes)}/{self.cap} notes used.")

    def _forget(self, args: dict[str, Any]) -> str:
        idx = self._parse_id(args)
        if idx is None:
            self._refused("no id")
            return (f"`id` must be a number between 1 and {len(self.notes)}."
                    if self.notes else "`id` must be a number (you have no notes).")
        if not 1 <= idx <= len(self.notes):
            self._refused("no such note")
            return (f"there is no note [{idx}]. You have {len(self.notes)}: "
                    f"use a number between 1 and {len(self.notes)}.")
        gone = self.notes.pop(idx - 1)
        self._kept(dropped=gone)
        return (f"forgotten: {gone[:60]}. "
                f"{len(self.notes)}/{self.cap} notes used, and they have "
                f"been renumbered.")

    # ------------------------------------------------------------ internal

    @staticmethod
    def _parse_id(args: dict[str, Any]) -> int | None:
        """Extracts the note id from args, tolerating string digits."""
        try:
            return int(args.get("id"))
        except (TypeError, ValueError):
            return None

    def _kept(self, **what: Any) -> None:
        """Marks the last logged call as having changed the notes."""
        if self.tool_log:
            self.tool_log[-1]["kept"] = len(self.notes)
            for k, v in what.items():
                if v:
                    self.tool_log[-1][k] = str(v)[: self.note_chars]

    def _refused(self, why: str) -> None:
        """Marks the last logged call as refused."""
        if self.tool_log:
            self.tool_log[-1]["refused"] = why
            self.tool_log[-1]["kept"] = len(self.notes)
