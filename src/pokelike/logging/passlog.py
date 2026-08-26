"""Progress logging for a running pass, writing one line per finished run and flushing live.

The log is a readable text file with aligned columns, suitable for `tail -f`.
Full structured data lives in the result; this file is the human-readable view.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .heartbeat import HeartbeatThread

# LEARN_K is the number of runs at each end of a pass used for the learning comparison.
LEARN_K = 10


class PassLog:
    """Writes one line per finished run, flushed as each run completes.

    This class accepts both the generalised form (folder, stem, seeds, workers,
    header_lines, memory) and the legacy positional form (version, model, seeds,
    workers) used by the model benchmark.
    """
    # Each line is flushed immediately because a buffered log is useless for
    # in-progress monitoring and loses the ending if the process dies.

    COLUMNS = ("  seed  badges   score  steps        in       out  fell  retry     secs")
    COLUMNS_MEMORY = COLUMNS + "  notes"
    COLUMNS_REGION = ("  seed  region   badges   score  steps        in       out  fell  retry     secs")
    COLUMNS_REGION_MEMORY = COLUMNS_REGION + "  notes"

    def __init__(self, version: str, model: str, seeds: list[int], workers: int,
                 memory: bool = False, folder: Path | None = None,
                 attempt: int = 1,
                 # When the generalised parameters are given, the caller owns the
                 # vocabulary. Otherwise legacy model-benchmark defaults apply.
                 stem: str | None = None,
                 header_lines: list[str] | None = None,
                 done_summary: Any = None,
                 notebook_header: str | None = None,
                 plan_header: str | None = None,
                 region: str | None = None) -> None:
        # The legacy default uses the model benchmark's session directory.
        if folder is None:
            from ..harness.llmbench.command import session_dir
            folder = session_dir(version)

        # The stem is provided explicitly, or built from the model slug + attempt.
        if stem is None:
            from ..harness.llmbench.versions import slug
            stem = f"{slug(model)}-pass{attempt}"

        self.path = folder / f"{stem}.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.started = time.time()
        self.n = 0
        self.total = len(seeds)
        self.badges: list[int] = []
        self.memory = memory
        # The region column is shown only when the pass is not Kanto.
        self.region = region
        self.model = model
        self.book: list[str] = []
        self.spent: dict[int, tuple[int, int]] = {}
        self.fh = self.path.open("w", encoding="utf-8", buffering=1)
        # This is the per-decision JSONL trace.
        self.trace_path = self.path.with_suffix(".jsonl")
        self.tf = self.trace_path.open("w", encoding="utf-8", buffering=1)
        # The notebook and plan files are opened on demand.
        self.book_path = self.path.with_name(self.path.stem + "-notebook.log")
        self.plan_path = self.path.with_name(self.path.stem + "-plan.log")
        self.summary_path = self.path.with_name(self.path.stem + "-summary.log")
        # These are per-run JSON lines (score, badges, etc.).
        self.runs_path = self.path.with_name(self.path.stem + "-runs.jsonl")
        self.bf: Any = None
        self.pf: Any = None
        self.sf: Any = None
        self.rf: Any = None
        self._last_book: list[str] | None = None
        self._last_plan: str | None = None
        self._notebook_header = notebook_header
        self._plan_header = plan_header
        self._done_summary = done_summary

        # The header uses caller-provided lines, or the legacy model-benchmark default.
        if header_lines is not None:
            for line in header_lines:
                self._say(line)
        else:
            self._say(f"{datetime.now():%Y-%m-%d %H:%M:%S}  harness {version}  {model}")
            self._say(f"{len(seeds)} seeds, {workers} worker{'s' if workers != 1 else ''}, "
                      f"seeds {seeds[0]}..{seeds[-1]}")
            if memory:
                self._say("this harness keeps the model's notes between runs: they are "
                          "logged as they change.")
        self._say(self._columns_header())

        # The liveness heartbeat keeps the .alive file fresh for watchers.
        self.alive_path = self.trace_path.with_suffix(".alive")
        self._heartbeat = HeartbeatThread(self.alive_path)
        self._heartbeat.start()

    @property
    def stamp(self) -> str:
        """Returns the pass's directory name, used as its identifier."""
        return self.path.parent.name

    def _say(self, line: str) -> None:
        self.fh.write(line + "\n")

    def _columns_header(self) -> str:
        """Returns the column header, including the region column when the pass is not Kanto."""
        if self.region and self.region != "kanto":
            return self.COLUMNS_REGION_MEMORY if self.memory else self.COLUMNS_REGION
        return self.COLUMNS_MEMORY if self.memory else self.COLUMNS

    def run(self, row: dict[str, Any]) -> None:
        """Records one finished run to the log and flushes immediately."""
        self.n += 1
        self.badges.append(row.get("badges") or 0)
        self.spent[row.get("seed")] = (row.get("tokens_in") or 0,
                                       row.get("tokens_out") or 0)
        # The region column is shown only when the pass is not Kanto.
        region_cell = ""
        if self.region and self.region != "kanto":
            region_cell = f"{(row.get('region') or self.region)[:7]:>9}"
        self._say(
            f"{row.get('seed', 0):>6}{region_cell}{row.get('badges') or 0:>8}"
            f"{(row.get('score') if row.get('score') is not None else 0):>8}"
            f"{row.get('steps') or 0:>7}"
            f"{row.get('tokens_in') or 0:>10}{row.get('tokens_out') or 0:>10}"
            f"{row.get('fallbacks') or 0:>6}{row.get('retries') or 0:>7}"
            f"{row.get('secs') or 0:>9.1f}"
            + (f"{row.get('notes_kept') or 0:>7}" if self.memory else "")
            + ("   <- fell back" if (row.get("fallbacks") or 0) else "")
            + ("   <- STALLED" if row.get("stalled") else "")
        )
        if self.memory and "notebook" in row:
            book = list(row["notebook"])
            for note in [x for x in book if x not in self.book]:
                self._say(f"       + {note}")
            for note in [x for x in self.book if x not in book]:
                self._say(f"       - {note}")
            self.book = book
        self._write_notebook(row)
        self._write_summary(row)
        self._write_plan(row)
        self._write_run_row(row)
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
        """Writes the summary line at the end of a successful pass."""
        # If a custom done_summary callable was given, delegate to it.
        if self._done_summary is not None:
            self._done_summary(self, one_pass)
            return

        # This writes the legacy model-benchmark summary.
        from ..harness.llmbench.results import learning

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

    def _write_run_row(self, row: dict[str, Any]) -> None:
        """Appends one JSON line per finished run to the `<pass>-runs.jsonl` file."""
        if self.rf is None:
            self.rf = self.runs_path.open("w", encoding="utf-8", buffering=1)
        self.rf.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _write_notebook(self, row: dict[str, Any]) -> None:
        """Writes the notes as they stood when this run ended."""
        book = row.get("notebook")
        if book is None:
            return
        if self.bf is None:
            self.bf = self.book_path.open("w", encoding="utf-8", buffering=1)
            header = (self._notebook_header
                      or f"notes {self.model} kept between runs\n"
                         f"one block per finished run, in the order played\n")
            self.bf.write(header + "\n")
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
        """Writes the route the bot had committed to when this run ended."""
        plan = row.get("plan")
        if plan is None:
            return
        if self.pf is None:
            self.pf = self.plan_path.open("w", encoding="utf-8", buffering=1)
            header = (self._plan_header
                      or f"the route {self.model} planned for each map\n"
                         f"as it stood when the run ended\n")
            self.pf.write(header + "\n")
        head = f"run {self.n:>2}  seed {row.get('seed')}"
        if plan == self._last_plan:
            self.pf.write(f"{head}  unchanged\n")
        elif not plan:
            self.pf.write(f"{head}  (none: it never called plan)\n")
        else:
            self.pf.write(f"{head}\n  {plan}\n")
        self._last_plan = plan

    def _write_summary(self, row: dict[str, Any]) -> None:
        """Writes what the finished run told the next one, one block per run.

        The file exists so the account a model builds of its own play can be read
        straight through, in the order the runs were played. A harness that writes no
        summary produces no file.
        """
        said = row.get("run_summary")
        if said is None:
            return
        if self.sf is None:
            self.sf = self.summary_path.open("w", encoding="utf-8", buffering=1)
            self.sf.write(f"what each run of {self.model} told the next one\n"
                          f"one block per finished run, in the order played\n\n")
        head = f"run {self.n:>2}  seed {row.get('seed')}  ({row.get('badges') or 0} badges)"
        self.sf.write(f"{head}\n  {said or '(nothing: the model wrote no summary)'}\n")

    def decision(self, e: dict[str, Any]) -> None:
        """Writes one decision as a JSON line to the trace file."""
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
            # Optional fields are included only when the enrichment provides them.
            **({"region": e["region"]} if e.get("region") else {}),
            **({"tools": e["tools"]} if e.get("tools") else {}),
            **({"map_view": e["map_view"]} if e.get("map_view") else {}),
            "turn_in": max(run_in - was_in, 0),
            "turn_out": max(run_out - was_out, 0),
            "run_in": run_in,
            "run_out": run_out,
            "pass_in": pass_in,
            "pass_out": pass_out,
        }, ensure_ascii=False) + "\n")

    def fail(self, why: str) -> None:
        """Records a failure line to the log."""
        self._say(f"FAILED after {self.n} runs: {why}")

    def stopped(self, why: str) -> None:
        """Records that the pass was stopped intentionally, not by an error."""
        self._say(f"STOPPED after {self.n} runs: {why}")

    def close(self) -> None:
        """Stops the heartbeat and closes all open file handles."""
        self._heartbeat.stop()
        for fh in (self.fh, self.tf, self.bf, self.pf, self.sf, self.rf):
            if fh is not None and not fh.closed:
                fh.close()

    def __enter__(self) -> "PassLog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
