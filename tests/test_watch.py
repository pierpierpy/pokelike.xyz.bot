"""The dashboard's reader, against a trace built here.

This runs in process, with `BENCH` pointed at a tmp directory, because the real
`llm-bench/` directory is gitignored. On a fresh checkout there is no pass to read
yet, which is exactly the state CI runs in. What is worth testing is the parsing,
and that needs a file, not a run.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from pokelike.harness import watch
from pokelike.harness.watch.read import newest_trace


def _trace(folder, model: str, rows: list[dict], alive: bool | float = True) -> None:
    """Write a pass's files. The `alive` parameter controls the heartbeat that
    decides liveness.

    True  -> a fresh .alive (a pass being played right now)
    False -> no .alive at all (a pass from an image older than the heartbeat)
    a timestamp -> a .alive with that mtime (a pass whose process has stopped)
    """
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "command.json").write_text(json.dumps({
        "at": "2026-08-20T17:00:00+02:00", "harness": folder.parent.parent.name,
        "models": [model], "runs": 3, "seeds": [10000, 10001, 10002], "workers": 1,
    }), encoding="utf-8")
    name = model.replace("/", "--")
    (folder / f"{name}-pass1.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    beat = folder / f"{name}-pass1.alive"
    if alive is True:
        beat.touch()
    elif alive is not False:
        beat.touch()
        os.utime(beat, (float(alive), float(alive)))


def _row(seed: int, step: int, at: str, **kw) -> dict:
    row = {"at": at, "seed": seed, "step": step, "screen": "map-screen", "map": 0,
           "badges": 0, "chose": 0, "action": "catch#n1_0", "options": ["a", "b"],
           "why": "because", "run_in": 1000, "run_out": 100}
    row.update(kw)
    return row


@pytest.fixture
def bench(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "BENCH", tmp_path)
    return tmp_path


def test_a_seed_that_has_moved_on_is_a_finished_run(bench):
    """Grouping by seed is what tells a finished run from the one in flight.

    The grouping is read from the trace, not from the columns of the human log.
    """
    _trace(bench / "v9" / "logs" / "20260820-170000", "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00"),
        _row(10000, 1, "2026-08-20T17:00:30", badges=2),
        _row(10001, 0, "2026-08-20T17:01:00"),
    ])
    p = watch.read(bench / "v9" / "logs" / "20260820-170000")
    assert p is not None
    assert p.model == "a/b"
    assert [r.seed for r in p.runs] == [10000, 10001]
    # The last seed is being played, so it is not counted as done.
    assert p.done == 1
    assert p.current is not None and p.current.seed == 10001
    first = p.runs[0]
    assert first.badges == 2 and first.steps == 2 and first.secs == 30.0


def test_a_fallback_is_counted_from_the_reason(bench):
    _trace(bench / "v9" / "logs" / "20260820-170000", "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00", why="(fell back: LLMError: HTTP 400)"),
        _row(10000, 1, "2026-08-20T17:00:01"),
        _row(10001, 0, "2026-08-20T17:00:02"),
    ])
    p = watch.read(bench / "v9" / "logs" / "20260820-170000")
    assert p.runs[0].fell == 1


def test_a_half_written_line_is_skipped_not_fatal(bench):
    """The last line is being written while this reads. The line arrives whole a moment later."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    f = d / "a--b-pass1.jsonl"
    f.write_text(f.read_text(encoding="utf-8") + '{"seed": 10001, "st',
                 encoding="utf-8")
    p = watch.read(d)
    assert [r.seed for r in p.runs] == [10000]


def test_the_state_comes_from_the_log_and_not_from_the_trace_stopping(bench):
    """A trace that stops looks the same whether the pass ended or the container died.
    The state must come from the log itself."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    assert watch.read(d).state == "running"
    (d / "a--b-pass1.log").write_text("header\ndone  1 runs  0.0 badges\n",
                                      encoding="utf-8")
    assert watch.read(d).state == "done"
    (d / "a--b-pass1.log").write_text("header\nFAILED after 1 runs: boom\n",
                                      encoding="utf-8")
    assert watch.read(d).state == "FAILED"


def test_wanted_is_never_less_than_what_was_played(bench):
    """Some older command files record `--seeds` as a range of two numbers.

    A pass that says it wanted 2 but played 50 reads as a broken pass rather than
    as a file being read the wrong way.
    """
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000 + i, 0, "2026-08-20T17:00:00") for i in range(5)])
    (d / "command.json").write_text(json.dumps(
        {"runs": 0, "seeds": [10000, 10004]}), encoding="utf-8")
    assert watch.read(d).wanted == 5


def test_the_notes_come_from_the_last_block_that_changed(bench):
    """The `unchanged` marker means the previous block still stands, so reading it
    must not clear the notes."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    (d / "a--b-pass1-notebook.log").write_text(
        "notes a/b kept between runs\n\n"
        "run  1  seed 10000  (1 notes)\n  [1] first\n"
        "run  2  seed 10001  (1 notes)  unchanged\n", encoding="utf-8")
    # Without its number, because the panel numbers them and a replayed operation and a note
    # read from the file have to be numbered by the same thing.
    assert watch.read(d).notes == ["first"]


def test_the_notes_shown_are_the_ones_it_holds_this_turn(bench):
    """The notebook file is per finished run, so a note written mid-run was invisible.

    A dashboard that said "nothing written yet" while the tool log on the line above
    showed a `remember` call is the reason this check exists.
    """
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00"),
        _row(10001, 0, "2026-08-20T17:00:10", tools=[
            {"tool": "remember", "note": "written this run", "kept": 2}]),
        _row(10001, 1, "2026-08-20T17:00:20", tools=[
            {"tool": "remember", "note": "refused, full", "refused": "notes full"},
            {"tool": "forget", "id": 1, "kept": 1},
        ]),
    ])
    (d / "a--b-pass1-notebook.log").write_text(
        "notes a/b kept between runs\n\n"
        "run  1  seed 10000  (1 notes)\n  [1] from a finished run\n", encoding="utf-8")
    p = watch.read(d)
    assert p.notes == ["from a finished run"], "the per-run file is still read"
    # The finished notebook, plus this run's operations, minus the refused one.
    assert p.notes_live == ["written this run"]


def test_newest_prefers_the_directory_written_to_last(bench):
    old = bench / "v9" / "logs" / "20260820-160000"
    new = bench / "v9" / "logs" / "20260820-170000"
    _trace(old, "a/b", [_row(10000, 0, "2026-08-20T16:00:00")])
    _trace(new, "c/d", [_row(10000, 0, "2026-08-20T17:00:00")])
    import os
    import time

    os.utime(old / "a--b-pass1.jsonl", (time.time() - 600, time.time() - 600))
    assert watch.newest() == new


def test_the_map_is_remembered_between_the_lines_that_carry_it(bench):
    """The map is written only when it changes, so the reader has to hold the last value."""
    d = bench / "v9" / "logs" / "20260820-170000"
    picture = "  layer  0 | [@]\n  layer  1 | <o> <x>"
    _trace(d, "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00", team=["Bulbasaur L5 19/19"],
             map_view=picture),
        _row(10000, 1, "2026-08-20T17:00:05", team=["Bulbasaur L5 12/19"]),
    ])
    r = watch.read(d).runs[0]
    assert r.map_view == picture, "the map was dropped on the line that omitted it"
    assert r.team == ["Bulbasaur L5 12/19"], "the team is the one at the last decision"


def test_a_trace_without_a_team_says_so_rather_than_inventing_one(bench):
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    r = watch.read(d).runs[0]
    assert r.team == [] and r.map_view == ""


def test_a_pass_can_be_chosen_by_stamp_or_by_model(bench):
    a = bench / "v9" / "logs" / "20260820-160000"
    b = bench / "v9" / "logs" / "20260820-170000"
    _trace(a, "a/b", [_row(10000, 0, "2026-08-20T16:00:00")])
    _trace(b, "c/d", [_row(10000, 0, "2026-08-20T17:00:00")])
    assert watch.pick(stamp="160000") == a
    assert watch.pick(model="c/d") == b
    assert watch.pick(stamp="nothing-like-this") is None


def test_with_two_running_and_nobody_to_ask_it_says_which_it_took(
        bench, capsys, monkeypatch):
    """Without a note about which was chosen, a number could be read as the other pass."""
    monkeypatch.setattr(watch, "_containers", lambda: [])
    a = bench / "v9" / "logs" / "20260820-160000"
    b = bench / "v9" / "logs" / "20260820-170000"
    _trace(a, "a/b", [_row(10000, 0, "2026-08-20T16:00:00")])
    _trace(b, "c/d", [_row(10000, 0, "2026-08-20T17:00:00")])
    assert len(watch.live()) == 2
    chosen = watch.pick()
    assert chosen == watch.newest()
    assert "2 passes going" in capsys.readouterr().out


def test_the_heartbeat_decides_what_is_live(bench, monkeypatch):
    """A pass is live while it is touching its heartbeat and dead the moment the
    heartbeat stops. Liveness is determined by the heartbeat file, independently of
    whether a container happens to be up.

    A stale heartbeat is a pass that stopped for some reason (a kill, an OOM, a
    power cut), and the dashboard must not offer it however recently the trace was
    written.
    """
    alive = bench / "v9" / "logs" / "20260820-170000"
    dead = bench / "v9" / "logs" / "20260820-150000"
    _trace(alive, "qwen/qwen3.7-flash", [_row(10000, 0, "2026-08-20T17:00:00")])
    _trace(dead, "google/gemma-4-31b-it", [_row(10000, 0, "2026-08-20T15:00:00")],
           alive=time.time() - 600)
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert watch.read(alive).state == "running"
    assert watch.read(dead).state == "stalled"
    assert {d.name for d in watch.live()} == {alive.name}


def test_a_fresh_heartbeat_is_live_without_any_container(bench, monkeypatch):
    """A pass played on the host has no container, so its heartbeat alone is enough."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert [x.name for x in watch.live()] == [d.name]


def test_a_pass_with_no_heartbeat_is_not_live(bench, monkeypatch):
    """No heartbeat means the pass is not running, even if a container of the same model is up.

    A container up for `qwen` cannot prove that a particular qwen pass is the one
    the container is running; a newer qwen pass could own it. The heartbeat is per
    pass, so the heartbeat is the only thing that answers the question, and its
    absence means the pass is dead.
    """
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "qwen/qwen3.7-flash", [_row(10000, 0, "2026-08-20T17:00:00")],
           alive=False)
    monkeypatch.setattr(watch, "_containers", lambda: ["pk_v4_qwen-qwen3-7-flash"])
    assert watch.live() == []
    assert watch.read(d, watch._containers()).state == "stalled"


def test_the_conversations_file_does_not_hide_the_trace(bench, monkeypatch):
    """A pass stays live when the file it writes most often is newer than its trace.

    The heartbeat's name is derived from whichever file is taken as the trace, and
    the conversations file shares the trace's stem with `-chat` added. That file is
    appended on every model call, so it is almost always the newest .jsonl in the
    folder. Taking it as the trace looks for a `-chat.alive` heartbeat that nothing
    writes, and a pass playing right now reads as stalled.
    """
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    chat = d / "a--b-pass1-chat.jsonl"
    chat.write_text('{"seed": 10000, "messages": []}\n', encoding="utf-8")
    later = time.time() + 10
    os.utime(chat, (later, later))
    monkeypatch.setattr(watch, "_containers", lambda: [])

    assert newest_trace(d).name == "a--b-pass1.jsonl"
    assert watch.read(d).state == "running"
    assert [x.name for x in watch.live()] == [d.name]


def test_a_finished_pass_is_not_offered_as_a_choice(bench, monkeypatch):
    """A dry run that ended three seconds ago should not be offered as something to follow.

    Being offered it was the confusing part. A one-run pass, done, appeared at the top
    of the list because the pass had written most recently.
    """
    a = bench / "v9" / "logs" / "20260820-160000"
    b = bench / "v9" / "logs" / "20260820-170000"
    _trace(a, "a/b", [_row(10000, 0, "2026-08-20T16:00:00")])
    _trace(b, "c/d", [_row(10000, 0, "2026-08-20T17:00:00")])
    (b / "c--d-pass1.log").write_text("header\ndone  1 runs\n", encoding="utf-8")
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert [d.name for d in watch.live()] == [a.name]
    # And with one left there is nothing to ask about.
    assert watch.pick() == a


def test_a_stale_pass_is_stalled_and_not_offered(bench, monkeypatch):
    """A pass whose heartbeat stopped is stalled and never offered to follow."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")], alive=time.time() - 600)
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert watch.read(d).state == "stalled"
    assert watch.live() == []


def test_the_numbers_in_the_list_do_not_move(bench, monkeypatch):
    """A number has to mean the same pass on two consecutive invocations.

    When ordered by last write (how everything else here is ordered), the list
    reshuffled between two invocations. The 3 chosen a minute ago was the 1 chosen
    now, and both were the same pass.
    """
    import os

    a = bench / "v9" / "logs" / "20260820-160000"
    b = bench / "v9" / "logs" / "20260820-170000"
    _trace(a, "a/b", [_row(10000, 0, "2026-08-20T16:00:00")])
    _trace(b, "c/d", [_row(10000, 0, "2026-08-20T17:00:00")])
    # a was launched first and is the one writing now, so the two orders disagree.
    (a / "command.json").write_text(json.dumps(
        {"at": "2026-08-20T16:00:00+02:00", "runs": 3}), encoding="utf-8")
    (b / "command.json").write_text(json.dumps(
        {"at": "2026-08-20T17:00:00+02:00", "runs": 3}), encoding="utf-8")
    older = time.time() - 30
    os.utime(b / "c--d-pass1.jsonl", (older, older))
    monkeypatch.setattr(watch, "_containers", lambda: [])

    assert watch.folders()[0] == a, "the fixture does not set up the disagreement"
    order = sorted(watch.live(), key=watch._started)
    assert [d.name for d in order] == [a.name, b.name]


def test_a_container_and_a_host_pass_sort_against_each_other(bench):
    """The stamps are two clocks two hours apart, so the directory name cannot be
    the sort key.

    A container writes UTC into the directory name and the host writes UTC+2. The
    `at` field in the command file carries its offset, which is why the sort reads
    that field.
    """
    utc = bench / "v9" / "logs" / "20260820-150000"
    host = bench / "v9" / "logs" / "20260820-163000"
    _trace(utc, "a/b", [_row(10000, 0, "2026-08-20T15:00:00")])
    _trace(host, "c/d", [_row(10000, 0, "2026-08-20T16:30:00")])
    (utc / "command.json").write_text(json.dumps(
        {"at": "2026-08-20T15:00:00+00:00", "runs": 3}), encoding="utf-8")
    (host / "command.json").write_text(json.dumps(
        {"at": "2026-08-20T16:30:00+02:00", "runs": 3}), encoding="utf-8")
    # 15:00 UTC is 17:00 in Rome, so the container pass started LAST.
    assert sorted([utc, host], key=watch._started) == [host, utc]


def test_nothing_running_is_not_a_finished_pass(bench, monkeypatch):
    """With nothing live, watch follows nothing and never the newest finished pass.

    A done (or stalled) pass shown as the thing you are watching is the exact
    confusion this removes. It looks like a live run that simply is not moving.
    """
    done = bench / "v9" / "logs" / "20260820-170000"
    _trace(done, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")], alive=False)
    (done / "a--b-pass1.log").write_text("header\ndone  1 runs\n", encoding="utf-8")
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert watch.live() == []
    assert watch.pick() is None
    # And the dashboard says so plainly rather than pointing at a missing trace.
    assert watch.dashboard(once=True) == 1


def test_nothing_to_watch_is_an_answer(bench):
    assert watch.dashboard(once=True) == 1
    assert watch.overview() == 1


def test_it_draws_what_it_read(bench):
    """The renderables are built, so a field renamed in the reader cannot go unnoticed."""
    from rich.console import Console

    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00"),
        # On the run in flight, which is the one the turn panel is about.
        _row(10001, 0, "2026-08-20T17:00:10",
             team=["Charmander L9 22/26", "Meowth L8 24/24"],
             map_view="  layer  0 | [@]\n  layer  1 | <o> <x>",
             tools=[{"tool": "remember", "note": "a lesson", "kept": 1},
                    {"tool": "play", "index": 0, "why": "because"}]),
    ])
    p = watch.read(d)
    out = Console(width=100, record=True, file=open("/dev/null", "w"))
    out.print(watch.render(p, ["a-container"]))
    text = out.export_text()
    assert "a/b" in text and "10000" in text
    assert "remember" in text and "a lesson" in text
    assert "Charmander L9 22/26" in text
    assert "layer  0" in text
    assert watch.dashboard(once=True) == 0
    assert watch.overview() == 0


# ------------------------------------------------------------------ the cost column
#
# Money is derived, never stored. The pass records tokens, and today's list price is
# applied to them when the table is drawn. So the column has to survive a price list
# that does not know the model, and must not turn a missing price into zero, which
# would read as free.


def test_the_cost_column_prices_the_tokens_counted_so_far(bench, monkeypatch):
    """A priced model shows what its finished runs have spent."""
    # importlib, because the package re-exports a function called `overview` that
    # shadows the submodule of the same name.
    import importlib
    ov = importlib.import_module("pokelike.harness.watch.overview")

    _trace(bench / "v9" / "logs" / "20260820-170000", "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00", run_in=1_000_000, run_out=100_000),
        _row(10001, 0, "2026-08-20T17:01:00", run_in=1, run_out=1),
    ])
    monkeypatch.setattr(ov, "_get_containers", lambda: [])
    # At $1 per million in and $10 per million out, the first run alone is 1 + 1 = $2.00.
    monkeypatch.setattr("pokelike.harness.llmbench.pricing.cached_prices",
                        lambda *a, **k: {"a/b": {"in": 1e-6, "out": 1e-5}})
    table, n = ov._running_table(None)
    assert n == 1
    assert [c.header for c in table.columns][6] == "cost", "cost sits beside the tokens"
    cells = [str(c) for c in table.columns[6]._cells]
    assert cells == ["$2.00"]


def test_a_model_with_no_price_shows_a_dash_not_zero(bench, monkeypatch):
    """An endpoint the price list has never heard of is unknown, and the cost cell
    must show a dash rather than zero."""
    # importlib, because the package re-exports a function called `overview` that
    # shadows the submodule of the same name.
    import importlib
    ov = importlib.import_module("pokelike.harness.watch.overview")

    _trace(bench / "v9" / "logs" / "20260820-170000", "local/qwen", [
        _row(10000, 0, "2026-08-20T17:00:00", run_in=500_000, run_out=9_000),
        _row(10001, 0, "2026-08-20T17:01:00"),
    ])
    monkeypatch.setattr(ov, "_get_containers", lambda: [])
    monkeypatch.setattr("pokelike.harness.llmbench.pricing.cached_prices",
                        lambda *a, **k: {"someone/else": {"in": 1e-6, "out": 1e-5}})
    table, _ = ov._running_table(None)
    assert "-" in str(table.columns[6]._cells[0])
    assert "$" not in str(table.columns[6]._cells[0])


def test_the_price_list_is_fetched_once_and_a_failure_is_not_cached(monkeypatch):
    """The live table redraws every couple of seconds, so the list must not be refetched
    each time. A failed fetch should be retried rather than remembered as empty."""
    from pokelike.harness.llmbench import pricing

    calls = []

    def fake_prices(*a, **k):
        calls.append(1)
        return {"a/b": {"in": 1.0, "out": 2.0}} if len(calls) > 1 else {}

    monkeypatch.setattr(pricing, "prices", fake_prices)
    monkeypatch.setattr(pricing, "_PRICE_CACHE", None)
    # The first call fails (offline), so nothing is cached and the next one tries again.
    assert pricing.cached_prices() == {}
    assert pricing.cached_prices() == {"a/b": {"in": 1.0, "out": 2.0}}
    assert len(calls) == 2
    # Now the value is cached, so no third fetch occurs.
    assert pricing.cached_prices() == {"a/b": {"in": 1.0, "out": 2.0}}
    assert len(calls) == 2


# ------------------------------------------------------------- stopping on purpose
#
# `model stop <stamp>` ends a pass the way docker stop does. Two things have to be
# true afterwards, because the pass reads as stopped (it was
# nobody's bug) and everything it wrote is still on disk.


def test_a_pass_stopped_on_purpose_is_not_read_as_a_failure(bench):
    """The word in the log distinguishes a deliberate stop from a crash."""
    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")], alive=False)
    log = folder / "a--b-pass1.log"
    log.write_text("2 seeds, 1 worker\nSTOPPED after 1 runs: SystemExit: 143\n",
                   encoding="utf-8")
    p = watch.read(folder)
    assert p is not None and p.state == "stopped"


def test_a_real_failure_still_reads_as_failed(bench):
    """The distinction has to cut both ways."""
    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")], alive=False)
    (folder / "a--b-pass1.log").write_text(
        "2 seeds, 1 worker\nFAILED after 1 runs: LLMConfigError: HTTP 401\n",
        encoding="utf-8")
    p = watch.read(folder)
    assert p is not None and p.state == "FAILED"


def test_the_stopper_resolves_a_stamp_prefix_and_refuses_an_ambiguous_one(bench):
    """A prefix is enough, unless it matches more than one pass."""
    import importlib
    stop = importlib.import_module("pokelike.interfaces.cli.commands.model_stop")

    for stamp in ("20260820-170000-aaaa", "20260820-170000-bbbb", "20260821-180000-cccc"):
        _trace(bench / "v9" / "logs" / stamp, "a/b",
               [_row(10000, 0, "2026-08-20T17:00:00")])
    assert stop._folder_for("20260821-18").name == "20260821-180000-cccc"
    assert stop._folder_for("20260820-17") is None, "two match, so it must refuse"
    assert stop._folder_for("19990101") is None, "none match"


def test_the_stopper_reads_who_owns_a_pass_from_the_heartbeat(bench):
    """A pass names its own process so that the right one is signalled."""
    import importlib
    stop = importlib.import_module("pokelike.interfaces.cli.commands.model_stop")

    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    (folder / "a--b-pass1.alive").write_text("pid=4242 host=7dae1e302082\n",
                                             encoding="utf-8")
    assert stop._owner(folder) == {"pid": "4242", "host": "7dae1e302082"}
    # A pass from before the owner line simply has nothing to say.
    (folder / "a--b-pass1.alive").write_text("", encoding="utf-8")
    assert stop._owner(folder) == {}


def test_a_recorded_pid_is_only_trusted_while_it_is_still_that_pass(bench):
    """Pids are reused, so the process behind a pid has to be checked."""
    import importlib
    import os
    stop = importlib.import_module("pokelike.interfaces.cli.commands.model_stop")

    # This test process is certainly not playing a benchmark.
    assert stop._mine(str(os.getpid()), "v9", "a/b") is False
    assert stop._mine("not-a-number", "v9", "a/b") is False
    assert stop._mine("999999999", "v9", "a/b") is False


def test_the_heartbeat_writes_who_is_playing(tmp_path):
    """The owner line is what makes a pass stoppable by name."""
    import os
    from pokelike.logging import HeartbeatThread

    beat = HeartbeatThread(tmp_path / "x.alive")
    assert f"pid={os.getpid()}" in beat.owner and "host=" in beat.owner


# ------------------------------------------------------------------- the score
#
# A run's score is the engine's own points_no_time, and the score exists only once
# the run is over. The score cannot come from the decision trace (one line per
# decision). The pass writes it to `<pass>-runs.jsonl`, which is also a .jsonl in
# the same folder, so the trace must never be found by "the newest .jsonl".


def _runs_file(folder, model: str, rows: list[dict]) -> None:
    """Writes the pass's runs file, one JSON line per finished run."""
    name = model.replace("/", "--")
    (folder / f"{name}-pass1-runs.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_a_finished_run_carries_its_score(bench):
    """The score reaches the table from the runs file, keyed by seed."""
    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [
        _row(10000, 0, "2026-08-20T17:00:00"),
        _row(10001, 0, "2026-08-20T17:01:00"),
    ])
    _runs_file(folder, "a/b", [{"seed": 10000, "score": -50, "badges": 1},
                               {"seed": 10001, "score": 15, "badges": 0}])
    p = watch.read(folder)
    assert p is not None
    assert {r.seed: r.score for r in p.runs} == {10000: -50, 10001: 15}


def test_the_runs_file_is_never_mistaken_for_the_trace(bench):
    """The runs file is a .jsonl in the same folder, and it is written last."""
    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [_row(10000, 0, "2026-08-20T17:00:00", badges=3)])
    # Written after the trace, so "newest .jsonl" would pick this one.
    _runs_file(folder, "a/b", [{"seed": 10000, "score": -50, "badges": 3}])
    os.utime(folder / "a--b-pass1-runs.jsonl", (time.time() + 10, time.time() + 10))
    p = watch.read(folder)
    assert p is not None
    assert p.model == "a/b"
    assert [r.badges for r in p.runs] == [3], "the decisions were parsed, not the runs"


def test_a_pass_without_a_runs_file_has_no_score_rather_than_a_wrong_one(bench):
    """Passes started before that file existed simply have nothing to show."""
    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    p = watch.read(folder)
    assert p is not None and p.runs[0].score is None


def test_a_pass_writes_its_runs_file_with_the_score(tmp_path):
    """The writing half: the row the result will hold is also written per run."""
    from pokelike.harness import llmbench as L

    folder = tmp_path / "20260821-000000-abcd"
    folder.mkdir()
    log = L.PassLog("v0", "a/b", [10000], workers=1, folder=folder)
    try:
        log.run({"seed": 10000, "badges": 2, "score": -35, "steps": 20,
                 "tokens_in": 1000, "tokens_out": 100, "secs": 5.0})
    finally:
        log.close()
    rows = [json.loads(x) for x in log.runs_path.read_text().splitlines() if x.strip()]
    assert rows == [{"seed": 10000, "badges": 2, "score": -35, "steps": 20,
                     "tokens_in": 1000, "tokens_out": 100, "secs": 5.0}]
    # And the human log grew a score column beside badges.
    assert "score" in L.PassLog.COLUMNS
    assert "-35" in log.path.read_text(encoding="utf-8")


# ------------------------------------------------- who is playing, and is it still there
#
# A pass writes `pid=... host=...` so the pass can be found and stopped, and the
# reader uses the same line to know at once when the pass is over instead of waiting
# out the heartbeat. The first version of that check lumped two cases together and
# got this wrong. A pass running outside a container writes this machine's hostname,
# which can never appear in a list of container names, so every local pass vanished
# from `model watch` the moment any container happened to be up. These tests lock
# the distinction.


def _pass_owned_by(bench, pid, host):
    """Create a running pass whose heartbeat names `pid` and `host`, then return
    the folder and the trace path."""
    folder = bench / "v9" / "logs" / "20260820-170000"
    _trace(folder, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    trace = folder / "a--b-pass1.jsonl"
    trace.with_suffix(".alive").write_text(f"pid={pid} host={host}\n", encoding="utf-8")
    return folder, trace


def test_a_pass_outside_a_container_is_not_killed_off_by_other_containers(bench):
    """The regression. A local pass is judged by its pid, never by the container list."""
    import importlib
    import os
    import socket
    rd = importlib.import_module("pokelike.harness.watch.read")

    folder, trace = _pass_owned_by(bench, os.getpid(), socket.gethostname())
    up = ["pk_v4_something", "5953fbc2470e"]
    assert rd._owner_gone(folder, up) is False
    assert watch.read(folder, up).state == "running"


def test_a_local_pass_whose_process_is_gone_is_over_at_once(bench):
    """The other half: the reader need not wait out the five-minute heartbeat when
    it can check the process directly."""
    import importlib
    import socket
    import subprocess
    import sys
    rd = importlib.import_module("pokelike.harness.watch.read")

    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    folder, trace = _pass_owned_by(bench, dead.pid, socket.gethostname())
    assert rd._owner_gone(folder, ["pk_v4_something"]) is True
    assert watch.read(folder, ["pk_v4_something"]).state != "running"


def test_a_container_pass_follows_its_container(bench):
    """A hostname that is not this machine is a container id."""
    import importlib
    rd = importlib.import_module("pokelike.harness.watch.read")

    folder, trace = _pass_owned_by(bench, 10, "5953fbc2470e")
    assert rd._owner_gone(folder, ["pk_v4_x", "5953fbc2470e"]) is False
    assert rd._owner_gone(folder, ["pk_v4_x", "aaaaaaaaaaaa"]) is True
    # Nothing to compare against is not evidence of death.
    assert rd._owner_gone(folder, []) is False


def test_a_pass_that_never_said_who_it_is_falls_back_to_the_heartbeat(bench):
    """Older passes wrote an empty heartbeat, and must keep working unchanged."""
    import importlib
    rd = importlib.import_module("pokelike.harness.watch.read")

    folder, trace = _pass_owned_by(bench, 10, "5953fbc2470e")
    trace.with_suffix(".alive").write_text("", encoding="utf-8")
    assert rd._owner_gone(folder, ["pk_v4_x"]) is False
    assert watch.read(folder, ["pk_v4_x"]).state == "running"
