"""The dashboard's reader, against a trace built here.

In process and with `BENCH` pointed at a tmp directory, because the real one is
gitignored: on a fresh checkout there is no pass to read, which is exactly the state
CI runs in. What is worth testing is the parsing, and that needs a file, not a run.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from pokelike.harness import watch


def _trace(folder, model: str, rows: list[dict], alive: bool | float = True) -> None:
    """Write a pass's files. `alive` controls the heartbeat that decides liveness:

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

    Read from the trace rather than from the columns of the human log, which is what
    the shell script this replaced parsed with `grep -c` and a fixed-width `cut`.
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
    """The last line is being written while this reads. It arrives whole a moment later."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    f = d / "a--b-pass1.jsonl"
    f.write_text(f.read_text(encoding="utf-8") + '{"seed": 10001, "st',
                 encoding="utf-8")
    p = watch.read(d)
    assert [r.seed for r in p.runs] == [10000]


def test_the_state_comes_from_the_log_and_not_from_the_trace_stopping(bench):
    """A trace that stops looks the same whether the pass ended or the container died."""
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

    A pass that says it wanted 2 and played 50 reads as a broken pass rather than as a
    file being read the wrong way.
    """
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000 + i, 0, "2026-08-20T17:00:00") for i in range(5)])
    (d / "command.json").write_text(json.dumps(
        {"runs": 0, "seeds": [10000, 10004]}), encoding="utf-8")
    assert watch.read(d).wanted == 5


def test_the_notes_come_from_the_last_block_that_changed(bench):
    """`unchanged` means the previous block still stands, so it must not clear it."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    (d / "a--b-pass1-notebook.log").write_text(
        "notes a/b kept between runs\n\n"
        "run  1  seed 10000  (1 notes)\n  [1] first\n"
        "run  2  seed 10001  (1 notes)  unchanged\n", encoding="utf-8")
    # Without its number: the panel numbers them, and a replayed operation and a note
    # read from the file have to be numbered by the same thing.
    assert watch.read(d).notes == ["first"]


def test_the_notes_shown_are_the_ones_it_holds_this_turn(bench):
    """The notebook file is per finished run, so a note written mid-run was invisible.

    A dashboard that said "nothing written yet" while the tool log on the line above it
    showed a `remember` is the reason this exists.
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
    """It is written only when it changes, so the reader has to hold the last one."""
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
    """The alternative is a number read as the other pass."""
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
    """A pass is live while it is touching its heartbeat, and dead the moment it
    stops -- not by the clock, and not by whether a container happens to be up.

    A stale heartbeat is a pass that stopped for SOME reason (a kill, an OOM, a
    power cut), and it must not be offered however recently the trace was written.
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
    """A pass played on the host has no container; its heartbeat is enough."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert [x.name for x in watch.live()] == [d.name]


def test_a_pass_with_no_heartbeat_is_not_live(bench, monkeypatch):
    """No heartbeat means not running, even if a container of the same model is up.

    A container up for `qwen` cannot prove that THIS qwen pass is the one it is
    running: a newer qwen pass could own it. The heartbeat is per pass, so it is
    the only thing that answers the question, and its absence is a dead pass.
    """
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "qwen/qwen3.7-flash", [_row(10000, 0, "2026-08-20T17:00:00")],
           alive=False)
    monkeypatch.setattr(watch, "_containers", lambda: ["pk_v4_qwen-qwen3-7-flash"])
    assert watch.live() == []
    assert watch.read(d, watch._containers()).state == "stalled"


def test_a_finished_pass_is_not_offered_as_a_choice(bench, monkeypatch):
    """A dry run that ended three seconds ago is not something to follow.

    It was, and being offered it was the confusing part: a one-run pass, `done`, top of
    the list because it had written most recently.
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
    """A pass whose heartbeat stopped is stalled, and never offered to follow."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")], alive=time.time() - 600)
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert watch.read(d).state == "stalled"
    assert watch.live() == []


def test_the_numbers_in_the_list_do_not_move(bench, monkeypatch):
    """A number has to mean the same pass twice in a row.

    Ordered by last write, which is how everything else here is ordered, the list
    reshuffled between two invocations: the 3 chosen a minute ago was the 1 chosen now,
    and both were the same pass.
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
    """The stamps are two clocks two hours apart, so the name cannot be the key.

    A container writes UTC into the directory name and the host writes UTC+2. The `at`
    in the command file carries its offset, which is why that is what this reads.
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
    """With nothing live, watch follows NOTHING -- never the newest finished pass.

    A `done` (or stalled) pass shown as the thing you are watching is the exact
    confusion this removes: it looks like a live run that simply is not moving.
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
