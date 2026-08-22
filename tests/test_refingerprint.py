"""Tests for utils/refingerprint.py."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

# Import the tool under test by path, since utils/ is not a package.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "refingerprint", Path(__file__).resolve().parents[1] / "utils" / "refingerprint.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

main = _mod.main
_scan_bots = _mod._scan_bots
_scan_llmbench = _mod._scan_llmbench
_apply_bot = _mod._apply_bot
_apply_llmbench = _mod._apply_llmbench


# ------------------------------------------------------------------- helpers


def _bot_fp(bot_dir: Path) -> str:
    """Reproduce the fingerprint logic for a bot folder."""
    h = hashlib.sha256()
    files = [bot_dir / "bot.py", *sorted((bot_dir / "artifacts").glob("**/*"))]
    for f in files:
        if not f.is_file():
            continue
        h.update(str(f.relative_to(bot_dir)).encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()


def _sha16(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def _make_bot(tmp_path: Path, name: str, code: str = "x = 1\n") -> Path:
    """Create a bot folder with bot.py and artifacts/."""
    d = tmp_path / "bots" / name
    d.mkdir(parents=True)
    (d / "bot.py").write_text(code)
    (d / "artifacts").mkdir()
    return d


def _make_bot_result(bot_dir: Path, fingerprint: str | None = None) -> Path:
    """Write a result.json with the given (or current) fingerprint."""
    fp = fingerprint if fingerprint is not None else _bot_fp(bot_dir)
    doc = {"bot": bot_dir.name, "fingerprint": fp, "summary": {"runs": 50}}
    r = bot_dir / "result.json"
    r.write_text(json.dumps(doc, indent=1))
    return r


def _make_llmbench(tmp_path: Path, version: str, model: str,
                   fp_dict: dict[str, str]) -> Path:
    """Create an llm-bench result file with a given fingerprint per pass."""
    rdir = tmp_path / "llm-bench" / version / "results"
    rdir.mkdir(parents=True, exist_ok=True)
    harness_dir = tmp_path / "llm-bench" / version / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    # Write frozen harness files so scanning works.
    for name in ("bot.py", "render.py", "bridge.js", "init.js"):
        (harness_dir / name).write_text(f"# {name}\n")
    slug = model.replace("/", "--")
    f = rdir / f"{slug}.json"
    doc = {
        "model": model,
        "harness": version,
        "passes": [{"fingerprint": fp_dict, "runs": []}],
    }
    f.write_text(json.dumps(doc, indent=1))
    return f


def _make_core(tmp_path: Path, browser: str = "b1", game: str = "g1",
               runner: str = "r1") -> None:
    """Create fake core files so _current_shared() works."""
    core = tmp_path / "src" / "pokelike" / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / "browser.py").write_text(browser)
    (core / "game.py").write_text(game)
    (core / "runner.py").write_text(runner)


# -------------------------------------------------------------------- tests


class TestBotMatching:
    """A bot whose fingerprint still matches is left alone."""

    def test_matching_bot_is_not_drifted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        d = _make_bot(tmp_path, "mybot")
        _make_bot_result(d)  # uses the current fingerprint
        entries = _scan_bots()
        assert len(entries) == 1
        assert entries[0]["match"] is True

    def test_drifted_bot_is_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        d = _make_bot(tmp_path, "mybot")
        _make_bot_result(d, fingerprint="0" * 64)  # wrong hash
        entries = _scan_bots()
        assert len(entries) == 1
        assert entries[0]["match"] is False
        assert entries[0]["recorded"] == "0" * 64


class TestLlmbenchMatching:
    """llm-bench passes that match are left alone, drifted ones are caught."""

    def test_matching_pass_is_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        _make_core(tmp_path)
        # Build fp_dict that matches what _current_shared + _current_frozen produce.
        harness_dir = tmp_path / "llm-bench" / "v0" / "harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        for name in ("bot.py", "render.py", "bridge.js", "init.js"):
            (harness_dir / name).write_text(f"# {name}\n")
        core = tmp_path / "src" / "pokelike" / "core"
        fp = {
            "bot.py": _sha16(b"# bot.py\n"),
            "render.py": _sha16(b"# render.py\n"),
            "bridge.js": _sha16(b"# bridge.js\n"),
            "init.js": _sha16(b"# init.js\n"),
            "shared/browser.py": _sha16(b"b1"),
            "shared/game.py": _sha16(b"g1"),
            "shared/runner.py": _sha16(b"r1"),
        }
        rdir = tmp_path / "llm-bench" / "v0" / "results"
        rdir.mkdir(parents=True, exist_ok=True)
        f = rdir / "test--model.json"
        f.write_text(json.dumps({
            "model": "test/model", "harness": "v0",
            "passes": [{"fingerprint": fp, "runs": []}],
        }, indent=1))
        entries = _scan_llmbench()
        assert len(entries) == 1
        assert entries[0]["match"] is True

    def test_drifted_shared_key_is_caught(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        _make_core(tmp_path)
        # Record an old hash for shared/game.py.
        harness_dir = tmp_path / "llm-bench" / "v0" / "harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        for name in ("bot.py", "render.py", "bridge.js", "init.js"):
            (harness_dir / name).write_text(f"# {name}\n")
        fp = {
            "shared/browser.py": _sha16(b"b1"),
            "shared/game.py": "aaaa" * 4,  # wrong
            "shared/runner.py": _sha16(b"r1"),
        }
        rdir = tmp_path / "llm-bench" / "v0" / "results"
        rdir.mkdir(parents=True, exist_ok=True)
        f = rdir / "test--model.json"
        f.write_text(json.dumps({
            "model": "test/model", "harness": "v0",
            "passes": [{"fingerprint": fp, "runs": []}],
        }, indent=1))
        entries = _scan_llmbench()
        assert len(entries) == 1
        assert entries[0]["match"] is False
        assert "shared/game.py" in entries[0]["drifted_keys"]


class TestDryRun:
    """A dry run writes nothing to disk."""

    def test_dry_run_does_not_modify(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        _make_core(tmp_path)
        d = _make_bot(tmp_path, "mybot")
        _make_bot_result(d, fingerprint="0" * 64)
        original = (d / "result.json").read_text()
        # Dry run (no --write).
        main(["--reason", "test", "--force"])
        assert (d / "result.json").read_text() == original


class TestApply:
    """When --write is given, drifted results are re-stamped with a log entry."""

    def test_bot_restamp_preserves_old_fingerprint(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        d = _make_bot(tmp_path, "mybot")
        old_fp = "0" * 64
        _make_bot_result(d, fingerprint=old_fp)
        main(["--reason", "test reason", "--write", "--force"])
        doc = json.loads((d / "result.json").read_text())
        # The fingerprint is now current.
        assert doc["fingerprint"] == _bot_fp(d)
        # The old one is preserved.
        assert len(doc["refingerprinted"]) == 1
        entry = doc["refingerprinted"][0]
        assert entry["was"]["fingerprint"] == old_fp
        assert entry["now"]["fingerprint"] == _bot_fp(d)
        assert entry["why"] == "test reason"
        assert "on" in entry

    def test_llmbench_restamp_preserves_old_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        _make_core(tmp_path)
        harness_dir = tmp_path / "llm-bench" / "v0" / "harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        for name in ("bot.py", "render.py", "bridge.js", "init.js"):
            (harness_dir / name).write_text(f"# {name}\n")
        old_game_hash = "dead" * 4
        fp = {
            "shared/browser.py": _sha16(b"b1"),
            "shared/game.py": old_game_hash,
            "shared/runner.py": _sha16(b"r1"),
        }
        rdir = tmp_path / "llm-bench" / "v0" / "results"
        rdir.mkdir(parents=True, exist_ok=True)
        f = rdir / "test--model.json"
        f.write_text(json.dumps({
            "model": "test/model", "harness": "v0",
            "passes": [{"fingerprint": fp, "runs": []}],
        }, indent=1))
        main(["--reason", "region support added", "--write", "--force"])
        doc = json.loads(f.read_text())
        p = doc["passes"][0]
        # Updated to current.
        assert p["fingerprint"]["shared/game.py"] == _sha16(b"g1")
        # Old preserved.
        assert len(p["refingerprinted"]) == 1
        entry = p["refingerprinted"][0]
        assert entry["was"] == {"shared/game.py": old_game_hash}
        assert entry["now"] == {"shared/game.py": _sha16(b"g1")}
        assert entry["why"] == "region support added"

    def test_matching_result_is_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        d = _make_bot(tmp_path, "mybot")
        _make_bot_result(d)  # current fingerprint
        original = (d / "result.json").read_text()
        main(["--reason", "should not appear", "--write", "--force"])
        assert (d / "result.json").read_text() == original


class TestSummary:
    """The printed summary has the right counts."""

    def test_counts_are_correct(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        _make_core(tmp_path)
        # One matching bot.
        d1 = _make_bot(tmp_path, "good")
        _make_bot_result(d1)
        # One drifted bot.
        d2 = _make_bot(tmp_path, "bad")
        _make_bot_result(d2, fingerprint="f" * 64)
        main(["--reason", "test", "--force"])
        out = capsys.readouterr().out
        assert "1 match" in out
        assert "1 drifted" in out


class TestDirtyTree:
    """Refuses to run on a dirty tree unless forced."""

    def test_refuses_dirty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        monkeypatch.setattr(_mod, "_tree_dirty", lambda: True)
        d = _make_bot(tmp_path, "mybot")
        _make_bot_result(d, fingerprint="0" * 64)
        with pytest.raises(SystemExit) as exc:
            main(["--reason", "test"])
        assert exc.value.code == 1

    def test_force_overrides_dirty(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        monkeypatch.setattr(_mod, "_tree_dirty", lambda: True)
        d = _make_bot(tmp_path, "mybot")
        _make_bot_result(d, fingerprint="0" * 64)
        # Should not raise.
        main(["--reason", "test", "--force"])
        out = capsys.readouterr().out
        assert "1 drifted" in out
