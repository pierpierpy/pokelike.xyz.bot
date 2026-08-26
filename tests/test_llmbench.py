"""Regression tests for the model benchmark.

These tests exist because the failures they cover happen quietly. A row that looks
comparable and is not, a fingerprint that certifies code it never ran, a credential
written into a file that gets committed. The failures that announce themselves need
no test; these do not.

Several of them pin behaviour in the frozen harnesses under `llm-bench/*/harness/`.
That is the point. Those files must not drift, and a test is a cheaper guard than
remembering.

No browser, no network, no model. The harnesses are loaded and inspected, and where
one has to be constructed the credentials are nonsense on purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pokelike.harness import llmbench as L
from pokelike.arena.bench import (STANDARD_SEEDS, _tok, live_fields,
                                        progress_bar)
from pokelike.bot import build, create
from pokelike.bot.catalogue import load_class
from pokelike.core.runner import short_label

OFFLINE = {"endpoint": "https://example.invalid", "token": "not-a-real-token"}


@pytest.fixture()
def memory_harness():
    """The frozen class of the harness that keeps notes, constructed offline.

    This is v4 today. The fixture is named for what it is rather than for its
    number, because v1 introduced the notebook and was deleted without ever being
    measured. A fixture called `memory_harness` only had to be read once to see
    which claim it was making.
    """
    cls = load_class(L.harness_path("v4"))
    return cls(seed=0, model="test-model", **OFFLINE)


@pytest.mark.parametrize("version,expected", [
    ("v0", {}),
    ("v2", {}),
    ("v4", {"notes": 12}),
    ("v6", {"notes": 40}),
    ("v7", {"notes": 40, "reasoning": None}),
    # v8 states both text budgets, so both are settable rather than only enforced.
    ("v8", {"notes": 40, "note_chars": 4000, "plan_chars": 1200, "reasoning": None}),
    # v9 changes the summary and the scratch line, and leaves the knobs alone.
    ("v9", {"notes": 40, "note_chars": 4000, "plan_chars": 1200, "reasoning": None}),
])
def test_each_version_reports_only_the_knobs_it_really_accepts(version, expected):
    """A knob is what the frozen constructor accepts, not what the class happens to hold.

    v2 carries a `NOTES_MAX` attribute and still refuses `--set notes=4`, because
    its constructor never pops that key and raises on anything left over. Reading
    the attribute instead of the constructor claimed a knob v2 does not have, which
    would have put a column of lies in the v2 table.
    """
    assert dict(L.version_settings(version)) == expected


def test_a_row_reports_the_default_for_a_knob_it_did_not_override():
    """Every row states what it ran with, so a blank never has to be interpreted."""
    assert L.settings_text("v7", None) == "notes=40,reasoning=off"
    assert L.settings_text("v7", {"reasoning": "high"}) == "notes=40,reasoning=high"
    assert L.settings_text("v6", {"notes": "4"}) == "notes=4"
    # A version with no knobs of its own contributes no column at all.
    assert L.settings_text("v2", None) == ""


def test_a_knob_added_by_a_later_version_needs_no_edit_here(monkeypatch):
    """A new `--set` key must reach every table and `model watch` on its own.

    Nothing lists the knobs by name, so a version that starts accepting one is
    picked up from its own constructor. The seven flags shared by every version
    stay out, since they say nothing about which question a row answers. The
    version named here is a real one, because only the class is being stood in
    for; the path still has to resolve.
    """
    from pokelike.bot import catalogue

    class Later:
        CACA = "on"
        TEMPERATURE = 0.7

        def __init__(self, **overrides):
            self.temperature = overrides.pop("temperature", self.TEMPERATURE)
            self.caca = overrides.pop("caca", self.CACA)

    monkeypatch.setattr(catalogue, "load_class", lambda *_a, **_k: Later)
    L.version_settings.cache_clear()
    try:
        assert dict(L.version_settings("v7")) == {"caca": "on"}
        assert L.settings_text("v7", None) == "caca=on"
        assert L.settings_text("v7", {"caca": "off"}) == "caca=off"
    finally:
        L.version_settings.cache_clear()


@pytest.mark.parametrize("version", L.versions())
def test_every_harness_is_loadable_and_reports_itself(version):
    """Catches what a mechanical copy gets wrong.

    v2 was generated from v1 and two references to `HarnessV1` survived the
    rename, one of them in `view_name()` -- so the class imported fine, played
    fine, and raised NameError only when a pass ended and asked it for its notes.
    Half an hour in, at the one moment there is a result to lose.
    """
    cls = load_class(L.harness_path(version))
    bot = cls(seed=0, model="test-model", **OFFLINE)
    notes = bot.metadata()
    assert notes["harness"] == cls.HARNESS
    assert "play" in bot.tool_names()
    assert [a.name for a in bot.artifacts()]
    assert bot.view_name()


@pytest.mark.parametrize("version", L.versions())
def test_every_harness_survives_a_committed_move(version):
    """The `_commit` method slices the journal with `self.memory`, so a version that gave that
    name to something else crashes on the first decision of the first run."""
    cls = load_class(L.harness_path(version))
    bot = cls(seed=0, model="test-model", **OFFLINE)
    state = {"actions": [{"kind": "menu", "label": "FIGHT"}], "team": None, "steps": 0}
    turns = abs(bot.MEMORY) + 3
    for k in range(turns):
        bot._commit(dict(state, steps=k), 0, f"reason {k}")
    # A negative MEMORY means an unbounded journal, and the slice that caps a positive
    # one silently empties an unbounded one (journal[1:] every turn), so both are held
    # here, because a version that gets this wrong remembers nothing and says nothing about it.
    if bot.MEMORY >= 0:
        assert len(bot.journal) == bot.MEMORY
    else:
        assert len(bot.journal) == turns


# --------------------------------------------------- what may be recorded
#
# A pass over anything other than the standard fifty seeds is not comparable to
# any other row, and nothing downstream can tell the difference once it is written.


def test_only_the_standard_seeds_may_be_recorded():
    assert L.records(STANDARD_SEEDS)
    assert L.records(list(STANDARD_SEEDS))          # a copy is the same measurement


def test_fifty_seeds_of_your_own_are_not_the_standard_fifty():
    """The bug this test replaced compared only lengths, so fifty seeds of your own
    would have been recorded."""
    mine = [s + 1000 for s in STANDARD_SEEDS]
    assert len(mine) == len(STANDARD_SEEDS)
    assert not L.records(mine)


def test_the_standard_seeds_shuffled_are_not_the_standard_seeds():
    """Order is part of the measurement under a harness that keeps notes."""
    assert not L.records(list(reversed(STANDARD_SEEDS)))


def test_a_partial_run_may_not_be_recorded():
    assert not L.records(STANDARD_SEEDS[:5])
    assert not L.records([])


# ------------------------------------------------------------ the fingerprint


def test_a_pass_records_the_fingerprint_it_was_given():
    """The fingerprint is taken before the first seed plays, not after the last one.

    Hashing at the end means an edit made during the pass produces a row that
    claims code it never ran and matches disk, so nothing can detect the edit. That
    is the inverse of what a fingerprint is for.
    """
    runs = [{"seed": 10000, "badges": 1, "turns": 20, "fallbacks": 0}]
    stamp = {"bot.py": "0" * 16, "render.py": "1" * 16}
    one = L._as_pass("v0", "m", [10000], runs, {}, {}, fingerprint=stamp)
    assert one["fingerprint"] == stamp


def test_a_pass_falls_back_to_hashing_disk_when_given_nothing():
    runs = [{"seed": 10000, "badges": 1, "turns": 20, "fallbacks": 0}]
    one = L._as_pass("v0", "m", [10000], runs, {}, {})
    assert one["fingerprint"] == L.fingerprints("v0")


def test_a_pass_is_named_by_its_log_directory(tmp_path):
    """The tuple (harness, model, stamp, seed) names one game, and the stamp is this.

    The standard fifty seeds are the same fifty for every model, so a seed alone
    names a game in every pass ever played. The stamp is the half that tells them
    apart, and the stamp is read off the directory so it cannot claim to be somewhere
    the files are not.
    """
    folder = tmp_path / "20260821-162048-1435"
    folder.mkdir()
    log = L.PassLog("v0", "a/b", [10000], workers=1, folder=folder)
    try:
        assert log.stamp == "20260821-162048-1435"
        assert log.path.parent == folder
    finally:
        log.close()


def test_a_changed_harness_marks_the_row_stale(tmp_path):
    """The mechanism that catches drift instead of absorbing it."""
    stamp = {"bot.py": "deadbeefdeadbeef", "render.py": "cafecafecafecafe"}
    one = L._as_pass("v0", "m", [10000], [{"seed": 10000, "badges": 1, "turns": 1,
                                           "fallbacks": 0}], {}, {}, fingerprint=stamp)
    assert L.stats({"model": "m", "passes": [one]}, "v0")["stale"] is True


def test_fingerprint_covers_what_decides_a_run_and_what_drives_it():
    """The fingerprint covers four frozen files and three shared ones.

    The frozen four decide what a run is: the loop, the text the model reads, the
    state the text is built from, and the pins that make a seed replay. The shared
    three drive the game, and are hashed rather than copied because copying them
    would mean each harness carrying its own browser plumbing.
    """
    for v in L.versions():
        keys = set(L.fingerprints(v))
        assert keys == {"bot.py", "render.py", "bridge.js", "init.js",
                        "shared/browser.py", "shared/game.py", "shared/runner.py"}


def test_the_frozen_files_all_live_in_the_harness_directory():
    """Frozen means nothing outside that folder can reach them."""
    for v in L.versions():
        here = L.harness_path(v).parent
        for p in (L.render_path(v), *L.script_paths(v).values()):
            assert p.parent == here, f"{p} is not frozen beside the harness"


def test_every_harness_carries_its_own_renderer():
    """The renderer is a copy per version, independent of the module the CLI improves.

    The renderer used to be `pokelike.core.render`, fingerprinted in the hope of
    catching drift rather than preventing it. That hope failed the first time the
    shared renderer had a defect. Fixing the defect for the person at the terminal
    would have marked every score ever recorded, so the benchmark was holding the
    CLI hostage.
    """
    for v in L.versions():
        p = L.render_path(v)
        assert p.is_file()
        assert p.parent == L.harness_path(v).parent
        assert "core" not in p.parts


def test_a_harness_without_its_own_scripts_is_an_error(tmp_path, monkeypatch):
    """A missing key is one nobody records and nobody checks, so absence must be loud."""
    monkeypatch.setattr(L, "BENCH", tmp_path)
    (tmp_path / "v9" / "harness").mkdir(parents=True)
    (tmp_path / "v9" / "harness" / "bot.py").write_text("x = 1\n")
    with pytest.raises(FileNotFoundError):
        L.render_path("v9")
    with pytest.raises(FileNotFoundError):
        L.script_paths("v9")
    with pytest.raises(FileNotFoundError):
        L.fingerprints("v9")

    (tmp_path / "v9" / "harness" / "render.py").write_text("y = 1\n")
    (tmp_path / "v9" / "harness" / "bridge.js").write_text("// b\n")
    with pytest.raises(FileNotFoundError, match="init.js"):
        L.script_paths("v9")


def test_adding_a_file_to_the_fingerprint_does_not_mark_older_results(monkeypatch):
    """The check compares key by key, so it answers "did anything move".

    Whole-dict equality answered "do we hash the same number of files as the day
    this ran", which is a different question and gets louder every time the
    fingerprint grows. One new file and every recorded row claims drift.
    """
    stamp = L.fingerprints("v0")
    one = L._as_pass("v0", "m", [10000], [{"seed": 10000, "badges": 1, "turns": 1,
                                           "fallbacks": 0}], {}, {}, fingerprint=stamp)
    assert L.stats({"model": "m", "passes": [one]}, "v0")["stale"] is False

    monkeypatch.setattr(L, "fingerprints",
                        lambda v: {**stamp, "shared/something-new.py": "0123456789ab"})
    assert L.stats({"model": "m", "passes": [one]}, "v0")["stale"] is False


def test_a_key_that_moved_is_still_caught_among_keys_that_did_not(monkeypatch):
    """The looser comparison must not become a way of not noticing."""
    stamp = L.fingerprints("v0")
    one = L._as_pass("v0", "m", [10000], [{"seed": 10000, "badges": 1, "turns": 1,
                                           "fallbacks": 0}], {}, {}, fingerprint=stamp)
    moved = {**stamp, "render.py": "ffffffffffffffff",
             "shared/something-new.py": "0123456789ab"}
    monkeypatch.setattr(L, "fingerprints", lambda v: moved)
    assert L.stats({"model": "m", "passes": [one]}, "v0")["stale"] is True


def test_a_key_no_longer_fingerprinted_is_not_read_as_drift(monkeypatch):
    """Dropping a file from the fingerprint is not evidence that it changed."""
    stamp = {**L.fingerprints("v0"), "gone.py": "aaaaaaaaaaaaaaaa"}
    one = L._as_pass("v0", "m", [10000], [{"seed": 10000, "badges": 1, "turns": 1,
                                           "fallbacks": 0}], {}, {}, fingerprint=stamp)
    assert L.stats({"model": "m", "passes": [one]}, "v0")["stale"] is False


# ------------------------------------------------- credentials stay out of files


def test_command_json_refuses_to_hold_a_credential(tmp_path):
    for field in ("api_key", "token", "FW_TOKEN", "secret", "authorization"):
        with pytest.raises(ValueError, match="refusing to write"):
            L.record_command(tmp_path, {"harness": "v0", field: "sk-or-v1-whatever"})
    assert not (tmp_path / "command.json").exists()


def test_command_json_keeps_the_endpoint(tmp_path):
    """The provider endpoint changes what the row means, so it must be kept."""
    p = L.record_command(tmp_path, {"harness": "v0", "models": ["a/b"],
                                    "endpoint": "https://openrouter.ai/api"})
    assert json.loads(p.read_text())["endpoint"] == "https://openrouter.ai/api"


def test_the_token_never_reaches_a_result_or_a_note(memory_harness):
    """The token has exactly one destination, the Authorization header."""
    blob = json.dumps(memory_harness.metadata()) + json.dumps(
        [a.data for a in memory_harness.artifacts() if a.data]
    )
    assert OFFLINE["token"] not in blob


# ------------------------------------------------------- cross-run memory (v1)


def test_v0_has_no_cross_run_memory_and_v4_does():
    assert L.cross_run_memory("v0") is False
    assert L.cross_run_memory("v4") is True


def test_a_memory_harness_refuses_to_be_split_across_workers():
    """Eight workers would mean eight notebooks over a fifth of the pass each, and
    a row that depends on how the seeds were dealt out."""
    with pytest.raises(RuntimeError, match="not independent"):
        L.fan_out("v4", "m", list(STANDARD_SEEDS), 8, Path("site"))


def test_the_notes_survive_the_end_of_a_run(memory_harness):
    """One line is the whole feature, so `on_start` must not clear the notes."""
    memory_harness._remember("remember", {"note": "trainer nodes pay off early"})
    kept = list(memory_harness.notebook)
    memory_harness.journal = ["step 3: [0] something"]

    memory_harness.reset(seed=12345)

    assert memory_harness.notebook == kept, "the notes are the point of this harness"
    assert memory_harness.journal == [], "the journal is per-run and must be cleared"


def test_memory_is_the_journal_size_and_the_notes_are_the_notebook(memory_harness):
    """The bug that nearly shipped made the notes take the name of the journal-trim
    size, and `_commit` slices the journal with that attribute."""
    assert isinstance(memory_harness.memory, int)
    assert memory_harness.memory == memory_harness.MEMORY
    assert isinstance(memory_harness.notebook, list)

    state = {"actions": [{"kind": "menu", "label": "FIGHT"}], "team": None, "steps": 0}
    for k in range(memory_harness.MEMORY + 4):
        memory_harness._commit(dict(state, steps=k), 0, f"reason {k}")
    assert len(memory_harness.journal) == memory_harness.MEMORY


@pytest.mark.parametrize(
    "verb,args,expect",
    [
        ("remember", {"note": "a lesson"}, "noted as [1]"),
        ("remember", {"note": "   "}, "nothing to remember"),
        ("revise", {"id": 9, "note": "x"}, "there is no note [9]"),
        ("revise", {"id": "two", "note": "x"}, "must be a number"),
        ("forget", {"id": 0}, "there is no note [0]"),
    ],
)
def test_the_memory_verbs_answer_instead_of_raising(memory_harness, verb, args, expect):
    """A model that gets an exception loses the turn to the fallback, while a model
    that gets a sentence carries on."""
    assert expect in memory_harness._remember(verb, args)


def test_a_note_is_truncated_rather_than_rejected(memory_harness):
    memory_harness._remember("remember", {"note": "x" * 500})
    assert len(memory_harness.notebook[0]) == memory_harness.NOTE_CHARS


def test_notes_are_capped_and_the_model_is_told_how_to_make_room(memory_harness):
    for i in range(memory_harness.NOTES_MAX):
        memory_harness._remember("remember", {"note": f"lesson {i}"})
    reply = memory_harness._remember("remember", {"note": "one more"})
    assert len(memory_harness.notebook) == memory_harness.NOTES_MAX
    assert "revise" in reply and "forget" in reply


def test_every_memory_reply_says_how_full_the_notebook_is(memory_harness):
    """Without it a model keeps calling `remember`, is refused, and behaves as
    though the lesson were saved."""
    cap = str(memory_harness.NOTES_MAX)
    assert cap in memory_harness._remember("remember", {"note": "one"})
    assert cap in memory_harness._remember("revise", {"id": 1, "note": "two"})
    assert cap in memory_harness._remember("forget", {"id": 1})


def test_the_notes_are_injected_above_the_journal(memory_harness):
    """Lessons learned across fifty runs outrank the last six turns of the current one."""
    memory_harness._remember("remember", {"note": "a lesson"})
    memory_harness.journal = ["step 3: [0] whatever"]
    text = memory_harness._situation({"actions": [{"kind": "menu", "label": "FIGHT"}],
                                  "team": None, "steps": 3})
    # The heading changed with the harness, because v0 to v2 said YOUR RECENT MOVES over the
    # model's own sentences while v4 separates what was done from what was said about it.
    assert 0 <= text.find("WHAT YOU HAVE LEARNED") < text.find("WHAT YOU DID")


def test_v1_offers_the_three_memory_tools_and_still_ends_a_turn_with_play(memory_harness):
    names = memory_harness.tool_names()
    assert {"remember", "revise", "forget"} <= set(names)
    assert "play" in names, "without it every turn falls back"


def test_notes_reported_per_run_are_a_copy(memory_harness):
    """The row is a snapshot of what it believed then, not a live handle."""
    memory_harness._remember("remember", {"note": "a lesson"})
    reported = memory_harness.metadata()["notebook"]
    reported.append("mutated")
    assert "mutated" not in memory_harness.notebook


def test_the_notes_and_the_plan_get_their_own_files(tmp_path, monkeypatch):
    """The notes and plan are readable on their own, because the question is how
    the model wrote them.

    The `unchanged` marker replaces a reprint when nothing moved. Fifty identical
    blocks would bury the three runs where the model actually learned something.
    """
    monkeypatch.setattr(L, "BENCH", tmp_path)
    log = L.PassLog("v2", "vendor/m", [10000, 10001, 10002], workers=1, memory=True)
    for seed, book, plan in (
        (10000, [], ""),
        (10001, ["a lesson worth keeping"], "down the left side, heal before the gym"),
        (10002, ["a lesson worth keeping"], "down the left side, heal before the gym"),
    ):
        log.run({"seed": seed, "badges": 1, "steps": 9, "tokens_in": 1, "tokens_out": 1,
                 "secs": 1.0, "notebook": book, "notes_kept": len(book), "plan": plan})
    log.close()

    book_text = log.book_path.read_text()
    assert "a lesson worth keeping" in book_text
    assert "(empty" in book_text, "a run where it wrote nothing has to say so"
    assert book_text.count("unchanged") == 1

    plan_text = log.plan_path.read_text()
    assert "heal before the gym" in plan_text
    assert "never called plan" in plan_text
    assert plan_text.count("unchanged") == 1


def test_a_harness_without_notes_leaves_no_empty_files(tmp_path, monkeypatch):
    """Two blank files per pass would be litter that reads like a bug."""
    monkeypatch.setattr(L, "BENCH", tmp_path)
    log = L.PassLog("v0", "vendor/m", [10000], workers=1)
    log.run({"seed": 10000, "badges": 1, "steps": 9, "tokens_in": 1, "tokens_out": 1,
             "secs": 1.0})
    log.close()
    assert not log.book_path.exists()
    assert not log.plan_path.exists()


@pytest.mark.parametrize("version", [v for v in L.versions() if v != "v0"])
def test_a_memory_harness_reports_the_plan_and_the_notes(version):
    """The wiring the two files depend on. Whatever notes() does not expose cannot
    reach a log, and both the notebook and the plan are read off notes() by name."""
    cls = load_class(L.harness_path(version))
    bot = cls(seed=0, model="test-model", **OFFLINE)
    keys = bot.metadata()
    assert "notebook" in keys
    if version != "v1":          # the plan arrives with v2
        assert "plan" in keys


# --------------------------------------------------------------- the learning curve


def _pass(badges, order=True):
    return {"runs": [{"seed": 10000 + i, "badges": b,
                      **({"order": i + 1} if order else {})}
                     for i, b in enumerate(badges)]}


def test_learning_is_the_last_ten_runs_against_the_first_ten():
    out = L.learning([_pass(list(range(50)))])
    assert out["first"] == 4.5 and out["last"] == 44.5 and out["delta"] == 40.0


def test_learning_is_measured_in_the_order_played_not_by_seed():
    """Rows are stored sorted by seed, but the fortieth run had thirty-nine runs of
    notes behind it."""
    rows = [{"seed": 10000 + i, "order": 50 - i, "badges": b}
            for i, b in enumerate(range(50))]
    assert L.learning([{"runs": rows}])["delta"] == -40.0


def test_learning_falls_back_to_seed_order_for_rows_recorded_without_it():
    assert L.learning([_pass(list(range(50)), order=False)])["delta"] == 40.0


def test_learning_needs_two_disjoint_ends():
    """Fewer than 2k runs means the two halves overlap, showing a gain that is the
    same runs counted twice."""
    assert L.learning([_pass([1] * 19)])["delta"] is None
    assert L.learning([])["delta"] is None


def test_learning_averages_per_pass_and_never_pools():
    """Pooling would compare one lifetime's start with another's end."""
    flat, climb = _pass([1] * 50), _pass(list(range(50)))
    assert L.learning([climb, flat])["delta"] == 20.0


def test_the_learn_column_appears_only_for_a_harness_that_keeps_notes(monkeypatch):
    doc = {"model": "m", "passes": [_pass(list(range(50)))]}
    for r in doc["passes"][0]["runs"]:
        r.update(tokens_in=1, tokens_out=1, turns=1, fallbacks=0, notes_kept=3)
    monkeypatch.setattr(L, "load", lambda v: [doc])
    assert "learn" in L.format_table("v4")
    assert "learn" not in L.format_table("v0")


# ---------------------------------------------------------------- the seed list


@pytest.mark.parametrize(
    "text,expected",
    [
        ("10010", [10010]),
        ("10010,10011", [10010, 10011]),
        ("10010-10013", [10010, 10011, 10012, 10013]),
        ("10049,10000-10001", [10049, 10000, 10001]),   # order as written
        (" 10010 , 10011 ", [10010, 10011]),
    ],
)
def test_parse_seeds(text, expected):
    from pokelike.interfaces.cli.shared import parse_seeds

    assert parse_seeds(text) == expected


@pytest.mark.parametrize("bad", ["", "10011-10010", "10010,10010"])
def test_parse_seeds_refuses_nonsense(bad):
    from pokelike.interfaces.cli.shared import parse_seeds

    with pytest.raises(ValueError):
        parse_seeds(bad)


# ------------------------------------------------------------------ credentials


class _Args:
    def __init__(self, **kw):
        self.__dict__.update({"endpoint": None, "api_key": None, "model": None, **kw})


def test_absent_flags_pass_nothing_through():
    """An absent flag must not become an empty string, because that would override
    the environment with nothing and turn a working setup into "FW_TOKEN is required"."""
    from pokelike.interfaces.cli.shared import llm_settings

    assert llm_settings(_Args()) == {}


def test_flags_are_forwarded_under_the_names_the_constructor_uses():
    from pokelike.interfaces.cli.shared import llm_settings

    got = llm_settings(_Args(endpoint="https://e", api_key="sk-x", model="m"))
    assert got == {"endpoint": "https://e", "token": "sk-x", "model": "m"}


def test_a_key_can_come_from_a_file(tmp_path):
    """A literal key is readable by every other user of the machine in `ps`."""
    from pokelike.interfaces.cli.shared import llm_settings

    f = tmp_path / "key"
    f.write_text("sk-from-a-file\n")
    assert llm_settings(_Args(api_key=f"@{f}")) == {"token": "sk-from-a-file"}


def test_a_missing_key_file_stops_the_command(tmp_path):
    from pokelike.interfaces.cli.shared import llm_settings

    with pytest.raises(SystemExit):
        llm_settings(_Args(api_key=f"@{tmp_path / 'nope'}"))


def test_the_environment_still_works_with_no_flags_at_all(monkeypatch):
    """The behaviour every existing script and fork depends on."""
    monkeypatch.setenv("FW_ENDPOINT", "https://from-env")
    monkeypatch.setenv("FW_TOKEN", "env-token")
    monkeypatch.setenv("MODEL_ID", "env-model")
    bot = create("llm-survivor")
    assert (bot.endpoint, bot.token, bot.model) == ("https://from-env", "env-token",
                                                    "env-model")


def test_flags_win_over_the_environment(monkeypatch):
    monkeypatch.setenv("FW_ENDPOINT", "https://from-env")
    monkeypatch.setenv("FW_TOKEN", "env-token")
    bot = create("llm-survivor", endpoint="https://from-flag", token="flag-token",
                 model="flag-model")
    assert (bot.endpoint, bot.token) == ("https://from-flag", "flag-token")


def test_a_bot_that_cannot_take_credentials_says_so_clearly():
    """Checked against the signature: a constructor raising TypeError for its own
    reasons must not be reported as being about credentials."""
    from pokelike.bot.random_bot import RandomBot

    with pytest.raises(TypeError, match="does not take"):
        build(RandomBot, endpoint="https://e")
    assert build(RandomBot).__class__ is RandomBot


# ------------------------------------------------------- what a pass writes down


def test_one_directory_per_command_with_a_numbered_log_per_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "BENCH", tmp_path)
    folder = L.session_dir("v0")
    logs = [L.PassLog("v0", "vendor/model-x", [10000, 10001], workers=1,
                      folder=folder, attempt=n) for n in (1, 2)]
    for lg in logs:
        lg.close()

    names = sorted(p.name for p in folder.iterdir())
    assert names == ["vendor--model-x-pass1.jsonl", "vendor--model-x-pass1.log",
                     "vendor--model-x-pass2.jsonl", "vendor--model-x-pass2.log"]
    assert folder.parent.name == "logs" and folder.parent.parent.name == "v0"


def test_results_do_not_live_in_the_command_directory():
    """One file per model with every pass appended is the comparable record; ten
    commands over three days build one model's history."""
    assert L.result_path("v0", "a/b").parent.name == "results"


def test_the_decision_trace_counts_tokens_at_three_levels(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "BENCH", tmp_path)
    log = L.PassLog("v0", "m", [10000, 10001], workers=2)

    def decide(seed, step, run_in, run_out):
        log.decision({"seed": seed, "step": step, "run_in": run_in,
                      "run_out": run_out, "chosen": 0, "chosen_label": "battle#3",
                      "options": ["battle#3"], "why": "because"})

    decide(10000, 1, 2_100, 900)
    decide(10001, 1, 1_800, 700)
    decide(10000, 2, 4_400, 1_950)
    log.run({"seed": 10000, "badges": 1, "tokens_in": 5_000, "tokens_out": 2_200})
    decide(10001, 2, 3_500, 1_500)
    log.close()

    rows = [json.loads(x) for x in log.trace_path.read_text().splitlines()]
    assert rows[2]["turn_in"] == 2_300, "the turn is the difference, not the total"
    assert rows[2]["run_in"] == 4_400
    # 5000 from the finished run plus 3500 still in flight on the other worker.
    assert rows[3]["pass_in"] == 8_500


def test_the_trace_says_which_option_it_took_and_why(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "BENCH", tmp_path)
    log = L.PassLog("v0", "m", [10000], workers=1)
    log.decision({"seed": 10000, "step": 3, "chosen": 1, "chosen_label": "catch#13",
                  "options": ["battle#12", "catch#13"], "why": "a second type",
                  "run_in": 1, "run_out": 1})
    log.close()
    row = json.loads(log.trace_path.read_text().splitlines()[0])
    assert row["chose"] == 1 and row["action"] == "catch#13"
    assert row["options"] == ["battle#12", "catch#13"] and row["why"] == "a second type"


def test_two_map_nodes_of_the_same_kind_are_distinguishable():
    """The trace once read `["tutor","tutor"]` beside a reason that argued about
    where each one led."""
    a = short_label({"kind": "node", "node": "move_tutor", "id": 14})
    b = short_label({"kind": "node", "node": "move_tutor", "id": 15})
    assert a != b and a == "tutor#14"


# ------------------------------------------------------------------ what is shown


def test_live_fields_report_depth_from_the_nodes():
    """The engine has no "how long is this map" field; the deepest layer is the
    boss, so layer 6 of 7 says what a step count cannot."""
    nodes = [{"id": f"n{i}", "layer": i} for i in range(8)]
    out = live_fields({"run": {"map": 1, "badges": 2},
                       "map": {"nodes": nodes, "current": "n6"}})
    assert out["layer"] == "6/7" and out["map"] == 1 and out["badges"] == 2


def test_live_fields_survive_a_screen_that_is_not_the_board():
    nodes = [{"id": "n0", "layer": 0}, {"id": "n1", "layer": 1}]
    assert live_fields({"map": {"nodes": nodes, "current": None}})["layer"] == "?/1"
    assert live_fields({})["badges"] == 0


def test_live_fields_only_mention_tokens_for_a_bot_that_spends_them():
    class Terse:
        tokens_in = tokens_out = fallbacks = 0

    assert "in" not in live_fields({}, Terse())


@pytest.mark.parametrize("n,text", [(0, "0k"), (21_000, "21k"), (999_499, "999k"),
                                    (999_500, "1.00M"), (1_580_000, "1.58M")])
def test_token_counts_are_short_enough_for_a_bar(n, text):
    assert _tok(n) == text


def test_the_bar_writes_whole_lines_when_nothing_is_watching(capsys, monkeypatch):
    """`docker compose run` allocates a pseudo-tty even with -d, so isatty cannot
    decide this. Carriage-return frames leave Docker's log driver holding an
    unterminated line, and `docker logs` shows nothing for the whole run.

    The postfix is also dropped because the live state of one run belongs on a bar
    you are watching, not repeated on every line of a file that already has the
    finished runs in it.
    """
    monkeypatch.setenv("POKELIKE_PLAIN_BAR", "1")
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True, raising=False)
    bar = progress_bar(total=2, desc="d", mininterval=0)
    bar.set_postfix({"badges": 0.75, "now": "10046@5/8"})
    bar.update(1)
    bar.close()
    err = capsys.readouterr().err
    assert err and "\r" not in err and err.endswith("\n")
    assert "badges" not in err and "now" not in err


def test_a_watched_bar_still_carries_the_live_state(capsys, monkeypatch):
    """The postfix is dropped only where nobody can see the bar change."""
    monkeypatch.delenv("POKELIKE_PLAIN_BAR", raising=False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True, raising=False)
    bar = progress_bar(total=2, desc="d", mininterval=0)
    bar.set_postfix({"badges": 0.75})
    bar.close()
    assert "badges" in capsys.readouterr().err


# ---------------------------------------------------------------- --set settings


def test_settings_are_typed_by_shape():
    """A command line has only strings, and `notes="4"` is a string where a number goes."""
    got = L.parse_settings(["notes=4", "temperature=0.7", "verbose=true", "who=me"])
    assert got == {"notes": 4, "temperature": 0.7, "verbose": True, "who": "me"}


def test_a_setting_without_a_value_is_refused():
    with pytest.raises(ValueError):
        L.parse_settings(["notes"])
    with pytest.raises(ValueError):
        L.parse_settings(["=4"])


def test_no_settings_is_an_empty_dict_not_a_none():
    """The return value is splatted into a constructor call, so it has to be a mapping."""
    assert L.parse_settings(None) == {}
    assert L.parse_settings([]) == {}


# ------------------------------------------------- what every harness must record


@pytest.mark.parametrize("version", L.versions())
def test_every_harness_records_the_tool_calls_it_makes(version):
    """The trace and the dashboard read tool_calls_made(). A version without this
    method logs less than v4.

    The method lives in each harness rather than in the shared side because the
    dispatch loop is the harness. The `play` and `set_lead` tools are handled
    inline and never reach `run_tool`, so a wrapper around that method from outside
    cannot see the decision itself. Three copies of one method is what a frozen copy
    means here.
    """
    cls = load_class(L.harness_path(version))
    bot = cls(seed=0, model="test-model", **OFFLINE)
    assert callable(getattr(bot, "tool_calls_made", None))

    bot._note_call("what_lies_ahead", {})
    bot._note_call("play", {"index": 2, "why": "because"})
    made = bot.tool_calls_made()
    assert [c["tool"] for c in made] == ["what_lies_ahead", "play"]
    assert made[1]["index"] == 2 and made[1]["why"] == "because"
    assert bot.tool_calls_made() == [], "asking must drain, or a turn is logged twice"


@pytest.mark.parametrize("version", L.versions())
def test_the_recorder_is_called_for_every_tool_the_model_asks_for(version):
    """In the dispatch loop, before the call runs, so an unknown name is recorded too."""
    src = L.harness_path(version).read_text(encoding="utf-8")
    loop = src[src.index("for c in calls:"):]
    assert "self._note_call(name, args)" in loop[:400], (
        f"{version} extracts the tool name and does not record it")


def test_a_finished_game_is_counted_separately_from_eight_badges():
    """Badges stop at 8, so a win has to be counted separately.

    A model that finishes the game scores the same badges as one that reaches
    the Elite Four and dies. The `won` field tells them apart.
    """
    # The engine has eight gym leaders and the Elite Four awards no badge, so 8
    # is the ceiling. A model that finishes the game scores the same as one that
    # reaches the Elite Four and dies.
    runs = [{"seed": s, "badges": 8, "turns": 80, "fallbacks": 0,
             "ending": "win-screen" if s == 10000 else "gameover-screen"}
            for s in (10000, 10001, 10002)]
    one = L._as_pass("v4", "a/b", [10000, 10001, 10002], runs, {}, {})
    row = L.stats({"model": "a/b", "harness": "v4", "passes": [one]})
    assert row["badges_best"] == 8
    assert row["badges_mean"] == 8.0, "badges cannot see the difference"
    assert row["won"] == 1, "the win can"
