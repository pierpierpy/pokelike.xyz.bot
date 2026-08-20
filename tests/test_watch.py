"""The dashboard's reader, against a trace built here.

In process and with `BENCH` pointed at a tmp directory, because the real one is
gitignored: on a fresh checkout there is no pass to read, which is exactly the state
CI runs in. What is worth testing is the parsing, and that needs a file, not a run.
"""

from __future__ import annotations

import json
import time

import pytest

from pokelike.instrument import watch


def _trace(folder, model: str, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "command.json").write_text(json.dumps({
        "at": "2026-08-20T17:00:00+02:00", "harness": folder.parent.parent.name,
        "models": [model], "runs": 3, "seeds": [10000, 10001, 10002], "workers": 1,
    }), encoding="utf-8")
    name = model.replace("/", "--")
    (folder / f"{name}-pass1.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


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


def test_the_containers_decide_what_is_live(bench, monkeypatch):
    """Three containers up means three passes to choose from, whatever the clock says.

    Deciding from the clock alone was wrong both ways: a pass killed a minute ago still
    looked alive, and one whose turn was taking six minutes looked dead.
    """
    dead = bench / "v9" / "logs" / "20260820-150000"
    alive = bench / "v9" / "logs" / "20260820-170000"
    other = bench / "v9" / "logs" / "20260820-170100"
    _trace(dead, "qwen/qwen3.7-flash", [_row(10000, 0, "2026-08-20T15:00:00")])
    _trace(alive, "qwen/qwen3.7-flash", [_row(10000, 0, "2026-08-20T17:00:00")])
    _trace(other, "google/gemma-4-31b-it", [_row(10000, 0, "2026-08-20T17:01:00")])
    import os

    old = time.time() - 120
    for f in dead.glob("*.jsonl"):
        os.utime(f, (old, old))

    monkeypatch.setattr(watch, "_containers", lambda: [
        "qwen-qwen3-7-flash-180247", "google-gemma-4-31b-it-180235"])
    names = {d.name for d in watch.live()}
    assert names == {alive.name, other.name}, "the killed pass is still being offered"


def test_a_model_with_no_container_of_its_own_is_dropped(bench, monkeypatch):
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "deepseek/deepseek-v4-flash-0731", [_row(10000, 0, "2026-08-20T17:00:00")])
    import os

    old = time.time() - 120
    for f in d.glob("*.jsonl"):
        os.utime(f, (old, old))
    monkeypatch.setattr(watch, "_containers", lambda: ["qwen-qwen3-7-flash-1"])
    assert watch.live() == []


def test_without_docker_the_clock_decides(bench, monkeypatch):
    """A pass played on the host has no container to be found in."""
    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert [x.name for x in watch.live()] == [d.name]


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


def test_a_pass_nothing_has_written_to_for_a_while_is_stalled(bench, monkeypatch):
    import os

    d = bench / "v9" / "logs" / "20260820-170000"
    _trace(d, "a/b", [_row(10000, 0, "2026-08-20T17:00:00")])
    old = time.time() - 600
    os.utime(d / "a--b-pass1.jsonl", (old, old))
    assert watch.read(d).state == "stalled"
    # Still offered with nothing containerised, because five minutes of silence is
    # not proof under a harness whose turns are this big. The state says so in the
    # list, and a container list is what settles it when there is one.
    monkeypatch.setattr(watch, "_containers", lambda: [])
    assert [x.name for x in watch.live()] == [d.name]


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
