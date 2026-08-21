"""Progress logging for a running pass: one line per finished run, flushed live.

A benchmark can run for hours. A progress bar is fine while you are watching it
and worth nothing afterwards: come back to a finished terminal and there is no
answer to "what did it do for three hours", "when did it start failing", or
"how much did that cost". So every pass writes a log beside its results.

Deliberately a readable text file rather than JSON. The rows themselves are
already stored, in full, in the result: this is the thing you `tail -f` from
another terminal, so it is aligned columns and nothing else.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .command import session_dir
from .heartbeat import HEARTBEAT_SECS, HEARTBEAT_STALE, HeartbeatThread
from .versions import slug

# How many runs at each end of a pass make up the learning comparison. Ten of
# fifty: long enough to average out a lucky seed, short enough that the two
# ends are actually early and late rather than two halves of the same curve.
LEARN_K = 10


class PassLog:
    """One line per finished run, flushed as it happens.

    In: version, model, seeds, worker count, optional memory/folder/attempt.
    Out: call run() per row, decision() per trace entry, done()/fail()/close().
    """
    # Flushed per line on purpose: a log that buffers tells you nothing about a run
    # still in progress, which is the only time you need it, and loses the ending if
    # the process dies: which is exactly the ending worth reading.
    #
    # In parallel, lines arrive in completion order rather than seed order, because
    # they are written as workers finish. That is not a defect: it is what tells you
    # a particular worker has been stuck on one game for two minutes.

    COLUMNS = ("  seed  badges  steps        in       out  fell  retry     secs")
    COLUMNS_MEMORY = COLUMNS + "  notes"

    def __init__(self, version: str, model: str, seeds: list[int], workers: int,
                 memory: bool = False, folder: Path | None = None,
                 attempt: int = 1) -> None:
        # The command's directory, made by the caller so that every pass of a
        # sweep lands in the same one. Created here when there is no caller to ask.
        folder = folder or session_dir(version)
        # Numbered rather than timestamped: inside one command the pass number is
        # what tells them apart, and it sorts correctly.
        self.path = folder / f"{slug(model)}-pass{attempt}.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.started = time.time()
        self.n = 0
        self.total = len(seeds)
        self.badges: list[int] = []
        # Last notebook seen, so the log can show what CHANGED rather than
        # reprinting twelve unchanged notes fifty times.
        self.memory = memory
        self.model = model
        self.book: list[str] = []
        # Per seed, the last (in, out) seen for it. Two jobs from one dict: the
        # difference against the previous reading is what a turn cost, and the sum
        # over every seed is what the pass has cost (including runs still in flight).
        self.spent: dict[int, tuple[int, int]] = {}
        self.fh = self.path.open("w", encoding="utf-8", buffering=1)
        # What the model decided and why, one JSON object per decision.
        # NOT in the result: twenty decisions a run times fifty runs would multiply
        # the size of a file whose job is to hold one comparable row per seed.
        self.trace_path = self.path.with_suffix(".jsonl")
        self.tf = self.trace_path.open("w", encoding="utf-8", buffering=1)
        # The two things the model WRITES, each in its own file, one block per run.
        # Opened on demand rather than up front: v0 has neither.
        self.book_path = self.path.with_name(self.path.stem + "-notebook.log")
        self.plan_path = self.path.with_name(self.path.stem + "-plan.log")
        self.bf: Any = None
        self.pf: Any = None
        self._last_book: list[str] | None = None
        self._last_plan: str | None = None
        self._say(f"{datetime.now():%Y-%m-%d %H:%M:%S}  harness {version}  {model}")
        self._say(f"{len(seeds)} seeds, {workers} worker{'s' if workers != 1 else ''}, "
                  f"seeds {seeds[0]}..{seeds[-1]}")
        if memory:
            self._say("this harness keeps the model's notes between runs: they are "
                      "logged as they change.")
        self._say(self.COLUMNS_MEMORY if memory else self.COLUMNS)

        # Liveness heartbeat.
        self.alive_path = self.trace_path.with_suffix(".alive")
        self._heartbeat = HeartbeatThread(self.alive_path)
        self._heartbeat.start()

    @property
    def stamp(self) -> str:
        """The pass's own name: its log directory.

        In: nothing. Out: the directory name string (e.g. '20260821-162048-1435').
        """
        # The identity of a pass, and the half of a run's identity that the seed does
        # not carry. Read off the directory rather than stored a second time, so it
        # cannot claim to be somewhere the files are not.
        return self.path.parent.name

    def _say(self, line: str) -> None:
        self.fh.write(line + "\n")

    def run(self, row: dict[str, Any]) -> None:
        """Records one finished run to the log.

        In: the run's result dict. Out: a line is written and flushed.
        """
        self.n += 1
        self.badges.append(row.get("badges") or 0)
        self.spent[row.get("seed")] = (row.get("tokens_in") or 0,
                                       row.get("tokens_out") or 0)
        self._say(
            f"{row.get('seed', 0):>6}{row.get('badges') or 0:>8}{row.get('steps') or 0:>7}"
            f"{row.get('tokens_in') or 0:>10}{row.get('tokens_out') or 0:>10}"
            f"{row.get('fallbacks') or 0:>6}{row.get('retries') or 0:>7}"
            f"{row.get('secs') or 0:>9.1f}"
            + (f"{row.get('notes_kept') or 0:>7}" if self.memory else "")
            + ("   <- fell back" if (row.get("fallbacks") or 0) else "")
            + ("   <- STALLED" if row.get("stalled") else "")
        )
        # What the model changed its mind about, when it did.
        if self.memory and "notebook" in row:
            book = list(row["notebook"])
            for note in [x for x in book if x not in self.book]:
                self._say(f"       + {note}")
            for note in [x for x in self.book if x not in book]:
                self._say(f"       - {note}")
            self.book = book
        self._write_notebook(row)
        self._write_plan(row)
        # A mark every ten runs, with where it is and when it should finish.
        if self.total and self.n % 10 == 0 and self.n < self.total:
            done = time.time() - self.started
            left = done / self.n * (self.total - self.n)
            self._say(
                f"  .. {self.n}/{self.total}  "
                f"badges {sum(self.badges) / len(self.badges):.2f}  "
                f"{done / 60:.0f} min in, about {left / 60:.0f} left, "
                f"done around {datetime.fromtimestamp(time.time() + left):%H:%M}"
            )

    def done(self, one_pass: dict[str, Any]) -> None:
        """Writes the summary line at the end of a successful pass.

        In: the assembled pass dict. Out: summary lines written to the log.
        """
        from .results import learning

        s = one_pass.get("summary") or {}
        mins = (time.time() - self.started) / 60
        fell = one_pass.get("fallback_rate", 0)
        self._say(
            f"done  {s.get('runs', self.n)} runs  {s.get('badges_mean')} badges  "
            f"{one_pass.get('tokens_in', 0) / 1e6:.2f}M in  "
            f"{one_pass.get('tokens_out', 0) / 1e6:.2f}M out  "
            f"fallback {fell}  retries {one_pass.get('retries', 0)}  "
            f"in {mins:.1f} min"
        )
        if fell > 0.1:
            self._say("WARNING fallback over 0.1: this row measures the harness, "
                      "not the model")
        if self.memory:
            lc = learning([one_pass])
            if lc.get("delta") is not None:
                self._say(f"first {lc['k']} runs {lc['first']} badges, "
                          f"last {lc['k']} {lc['last']}, so {lc['delta']:+} "
                          f"-- what this harness is for")
            self._say(f"notes it finished with ({len(self.book)}):")
            for i, note in enumerate(self.book, 1):
                self._say(f"  [{i}] {note}")

    def _write_notebook(self, row: dict[str, Any]) -> None:
        """One block per run: the notes as they stood when that run ended."""
        book = row.get("notebook")
        if book is None:
            return
        if self.bf is None:
            self.bf = self.book_path.open("w", encoding="utf-8", buffering=1)
            self.bf.write(f"notes {self.model} kept between runs\n"
                          f"one block per finished run, in the order played\n\n")
        head = f"run {self.n:>2}  seed {row.get('seed')}  ({len(book)} notes)"
        if book == self._last_book:
            self.bf.write(f"{head}  unchanged\n")
        else:
            self.bf.write(head + "\n")
            for i, note in enumerate(book, 1):
                self.bf.write(f"  [{i}] {note}\n")
            if not book:
                self.bf.write("  (empty: it wrote nothing)\n")
            self._last_book = list(book)

    def _write_plan(self, row: dict[str, Any]) -> None:
        """One block per run: the route it had committed to when the run ended."""
        plan = row.get("plan")
        if plan is None:
            return
        if self.pf is None:
            self.pf = self.plan_path.open("w", encoding="utf-8", buffering=1)
            self.pf.write(f"the route {self.model} planned for each map\n"
                          f"as it stood when the run ended\n\n")
        head = f"run {self.n:>2}  seed {row.get('seed')}"
        if plan == self._last_plan:
            self.pf.write(f"{head}  unchanged\n")
        elif not plan:
            self.pf.write(f"{head}  (none: it never called plan)\n")
        else:
            self.pf.write(f"{head}\n  {plan}\n")
        self._last_plan = plan

    def decision(self, e: dict[str, Any]) -> None:
        """Writes one decision as JSON to the trace file.

        In: decision dict (seed, step, screen, chose, options, why, etc.).
        Out: one JSON line appended to the .jsonl trace.
        """
        # Deliberately not the prompt, not the tool calls and not the rendered
        # screen: those are reconstructible from the harness plus the seed, they are
        # most of the bytes, and none of them is what you come here to read. What is
        # NOT reconstructible is which option it took and the sentence it gave for it.
        seed = e.get("seed")
        run_in, run_out = e.get("run_in") or 0, e.get("run_out") or 0
        was_in, was_out = self.spent.get(seed, (0, 0))
        self.spent[seed] = (run_in, run_out)
        pass_in = sum(v[0] for v in self.spent.values())
        pass_out = sum(v[1] for v in self.spent.values())

        self.tf.write(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            "seed": seed,
            "step": e.get("step"),
            "screen": e.get("screen"),
            "map": e.get("map"),
            "badges": e.get("badges"),
            "chose": e.get("chosen"),
            "action": e.get("chosen_label"),
            "options": e.get("options"),
            "swapped": e.get("swapped"),
            "why": e.get("why"),
            "team": e.get("team"),
            **({"tools": e["tools"]} if e.get("tools") else {}),
            **({"map_view": e["map_view"]} if e.get("map_view") else {}),
            # Three levels of the same two numbers.
            "turn_in": max(run_in - was_in, 0),
            "turn_out": max(run_out - was_out, 0),
            "run_in": run_in,
            "run_out": run_out,
            "pass_in": pass_in,
            "pass_out": pass_out,
        }, ensure_ascii=False) + "\n")

    def fail(self, why: str) -> None:
        """Records a failure line to the log.

        In: a description of the failure. Out: the line is written.
        """
        self._say(f"FAILED after {self.n} runs: {why}")

    def close(self) -> None:
        """Stops the heartbeat and closes all open file handles.

        In: nothing. Out: .alive removed, all handles closed.
        """
        self._heartbeat.stop()
        for fh in (self.fh, self.tf, self.bf, self.pf):
            if fh is not None and not fh.closed:
                fh.close()

    def __enter__(self) -> "PassLog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
