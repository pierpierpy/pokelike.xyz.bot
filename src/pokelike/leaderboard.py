"""The leaderboard: reading what each bot scored, and writing what one scored.

A bot is a folder under `bots/`, and its measurement lives in that same folder:

    bots/<name>/
    ├── bot.py        the code that ran
    ├── artifacts/    the weights, prompts or tables it needs
    └── result.json   the benchmark, with a fingerprint of both

Entries used to be separate immutable folders named `<slug>-<hash>`, one per
measurement. That kept every past result re-runnable from any checkout, and cost
a new folder each time anyone measured anything, plus a copy of a bot that
already existed. A bot is now one folder that evolves, and git holds its history.

WHAT THE FINGERPRINT IS FOR
A score means nothing without the code it came from. `result.json` records a
sha256 over `bot.py` and every artifact, so a result and the thing that produced
it cannot drift apart unnoticed: `pokelike leaderboard` says `stale` beside any
row whose files have changed since it was measured.

It also records the sha256 of the game bundle. Scores from before and after an
upstream game update are not comparable, and without it a table mixes them
silently.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bot.catalogue import BOTS, folder, slugify

# What an artifact is FOR, so a reader knows what they are looking at without
# opening it. Anything else is archived too, with a note.
KINDS = {
    "weights-json": "a trained policy, as JSON",
    "weights-remote": "weights hosted elsewhere, with a url and a sha256",
    "config": "how it was trained or configured",
    "prompt": "the text given to a language model",
    "notes": "anything else worth keeping beside the result",
}


@dataclass
class Artifact:
    """Something a bot needs, archived beside it.

    Give it `path` to copy a file, `data` to write a JSON document, or `text`
    to write it out as it is. A bot declares these from `artifacts()`, and the
    benchmark stores them.

    `text` exists because a prompt is prose. Putting one through `data` writes a
    JSON string, escapes every newline, and produces a prompt.md nobody can
    read -- which is the opposite of why it is archived. The LLM harness had
    been passing `text=` to a dataclass with no such field since it was written,
    and nothing noticed because artifacts() is only called by a complete
    benchmark and no LLM bot had ever finished one.
    """

    name: str
    kind: str
    description: str = ""
    path: Path | None = None
    data: Any = None
    text: str | None = None
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def write_into(self, folder: Path) -> dict[str, Any]:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / self.name
        if self.path is not None:
            # A bot's artifacts already live in its own folder, so "archiving"
            # them means copying a file onto itself -- which shutil refuses. It
            # is not an error: the file IS the artifact and it is already where
            # it belongs. It only became reachable when bots stopped being
            # copied into an archive and started being the archive.
            if Path(self.path).resolve() != target.resolve():
                shutil.copy2(self.path, target)
            elif not target.is_file():
                raise FileNotFoundError(f"artifact '{self.name}' is missing at {target}")
        elif self.data is not None:
            target.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        elif self.text is not None:
            target.write_text(self.text, encoding="utf-8")
        elif self.url is None:
            raise ValueError(
                f"artifact '{self.name}' has no path, data, text or url"
            )
        entry = {
            "name": self.name, "kind": self.kind, "description": self.description,
            **({"url": self.url} if self.url else {}), **self.extra,
        }
        if target.is_file():
            entry["bytes"] = target.stat().st_size
            entry["sha256"] = sha256_of(target)
        return entry


# ---------------------------------------------------------------- fingerprint


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def fingerprint(bot_dir: Path) -> str:
    """One hash over the bot's code and everything it carries.

    Covers `bot.py` and every file under `artifacts/`, each hashed with its name
    so that renaming a file changes the fingerprint too. This is what makes a
    recorded score checkable: re-hash the folder, compare, and you know whether
    the row still describes what is on disk.
    """
    h = hashlib.sha256()
    files = [bot_dir / "bot.py", *sorted((bot_dir / "artifacts").glob("**/*"))]
    for f in files:
        if not f.is_file():
            continue
        h.update(str(f.relative_to(bot_dir)).encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()


# -------------------------------------------------------------------- writing


def record_result(name: str, result: dict[str, Any], bot: Any,
                  root: Path | None = None) -> Path:
    """Writes `result.json` into the bot's own folder, artifacts included."""
    d = folder(name, root)
    if not (d / "bot.py").is_file():
        raise FileNotFoundError(
            f"{d} is not a bot: no bot.py.\n"
            f"Create one with:  uv run pokelike new-bot {slugify(name)}"
        )

    declared = list(getattr(bot, "artifacts", lambda: [])() or [])
    for a in declared:
        if a.kind not in KINDS:
            print(f"  note: artifact '{a.name}' has an unrecognised kind "
                  f"'{a.kind}', archiving it anyway")
    manifest = [a.write_into(d / "artifacts") for a in declared]

    document = {
        **result,
        "bot": slugify(name),
        # Written LAST, over the artifacts as they now are on disk.
        "fingerprint": fingerprint(d),
        "artifacts": manifest,
    }
    (d / "result.json").write_text(json.dumps(document, indent=1), encoding="utf-8")
    return d


# -------------------------------------------------------------------- reading


def load_results(root: Path | None = None) -> list[dict[str, Any]]:
    base = Path(root) if root else BOTS
    if not base.is_dir():
        return []
    out = []
    for f in sorted(base.glob("*/result.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  warning: {f} is not valid JSON, skipping")
            continue
        # The folder IS the name. A `bot` field left over from somewhere else
        # would let a row claim to be a bot it is not.
        r["bot"] = f.parent.name
        # Recomputed every time it is read, so a row cannot claim a score for
        # code that has since been edited without saying so.
        #
        # A result with NO fingerprint is not clean, it is unchecked -- it
        # predates the mechanism, or was hand-written. Reported separately rather
        # than folded into either bucket: calling it stale would be a claim we
        # cannot support, and calling it fine would be the silence the
        # fingerprint exists to prevent.
        r["unverified"] = not r.get("fingerprint")
        r["stale"] = bool(r.get("fingerprint")) and r["fingerprint"] != fingerprint(f.parent)
        out.append(r)
    return out


def build_index(root: Path | None = None) -> dict[str, Any]:
    """Regenerates index.json from whatever is measured on disk."""
    base = Path(root) if root else BOTS
    rows = []
    for e in load_results(base):
        s = e.get("summary") or {}
        notes = e.get("notes") or {}
        rows.append({
            "bot": e.get("bot"), "author": e.get("author"),
            "category": e.get("category"), "description": e.get("description"),
            "score_mean": s.get("score_mean"), "score_stdev": s.get("score_stdev"),
            "score_best": s.get("score_best"), "badges_mean": s.get("badges_mean"),
            "badges_best": s.get("badges_best"), "maps_mean": s.get("maps_mean"),
            "completed": s.get("completed"), "runs": s.get("runs"),
            "game": (e.get("game") or {}).get("sha256"),
            # LLM rows only. `model` says what actually answered -- a bot that
            # takes $MODEL_ID plays a different model for whoever ran it, so the
            # row is meaningless without it. `harness` and `fallback_rate` are
            # the two ways such a row can be true and still misleading.
            "model": notes.get("model"),
            "harness": notes.get("harness"),
            "fallback_rate": notes.get("fallback_rate"),
            "stock_tools": notes.get("stock_tools"),
            "state_view": notes.get("state_view"),
            "fingerprint": (e.get("fingerprint") or "")[:12],
            "stale": e.get("stale", False),
            "unverified": e.get("unverified", False),
            "artifacts": len(e.get("artifacts") or []),
        })
    # Ranked by badges, not score. The engine's score formula was written for the
    # Battle Tower and two of its six terms never fire in Story mode, so it
    # rewards fighting rather than getting further. See experiments/env/rewards.py.
    rows.sort(key=lambda r: (
        r["badges_mean"] is None, -(r["badges_mean"] or 0), -(r["score_mean"] or 0)
    ))
    index = {"entries": rows}
    base.mkdir(parents=True, exist_ok=True)
    (base / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    render_readme(base, index)
    return index


README_BEGIN = "<!-- BEGIN standings: generated by `pokelike leaderboard`, do not edit by hand -->"
README_END = "<!-- END standings -->"


def as_markdown(index: dict[str, Any]) -> str:
    """The standings as a markdown table, ranked by badges."""
    rows = index.get("entries") or []
    if not rows:
        return ("_No bots measured yet._ Yours would be the first, see "
                "[GUIDE.md](../GUIDE.md).\n")
    out = [
        "| # | bot | author | how | runs | badges~ | badges+ | score~ | best | code |",
        "|--:|---|---|---|--:|--:|--:|--:|--:|---|",
    ]
    for i, r in enumerate(rows, 1):
        n = lambda k, d="-": r[k] if r.get(k) is not None else d  # noqa: E731
        mark = " ⚠︎" if r.get("stale") else (" ?" if r.get("unverified") else "")
        out.append(
            f"| {i} | **[{r.get('bot')}]({r.get('bot')}/)** | {r.get('author') or '-'} "
            f"| {r.get('category') or '-'} | {n('runs', 0)} "
            f"| **{n('badges_mean')}** | {n('badges_best')} "
            f"| {n('score_mean')} | {n('score_best')} | `{r.get('fingerprint') or '-'}`{mark} |"
        )

    # An LLM row is true and still misleading unless three things are visible:
    # which model answered, which harness asked it, and how many turns it did
    # not actually decide. A fallback is our heuristic playing under the model's
    # name, so a row full of them measures us.
    llm = [r for r in rows if r.get("model")]
    if llm:
        out += ["", "**Models.**", "",
                "| bot | model | harness | sees | tools | fallback rate |",
                "|---|---|--:|---|---|--:|"]
        for r in llm:
            rate = r.get("fallback_rate")
            flag = " ⚠︎" if rate is not None and rate > 0.1 else ""
            stock = r.get("stock_tools")
            tools = "shared" if stock else ("own ⚠︎" if stock is False else "-")
            out.append(f"| {r.get('bot')} | `{r.get('model')}` | {r.get('harness', '-')} "
                       f"| {r.get('state_view') or '-'} | {tools} "
                       f"| {rate if rate is not None else '-'}{flag} |")
        out += ["",
                "An LLM result is **not reproducible**: providers change models behind a "
                "fixed name and sampling is stochastic. `fallback rate` is the share of "
                "turns the model did not decide, played instead by the harness's backup "
                "heuristic. **⚠︎ above 0.1 means the row is measuring us more than the "
                "model**. `harness` is the version of the shared loop in "
                "`pokelike/bot/llm.py`; rows measured under different numbers were not "
                "asked the same question. `tools` says whether the model was "
                "offered the shared four or a set of the bot's own. **Own ⚠︎ is "
                "not a fault**, it is a different question, and comparing it "
                "with the rest as though it were the same one is."]
    out += [
        "",
        "Ranked by **badges**, the game's own progress counter. `badges~` is the mean "
        "over the standard 50 seeds, `badges+` the best single run. `code` is a "
        "fingerprint over the bot and its artifacts; **⚠︎ means the files changed "
        "since the score was measured**, so the row no longer describes what is on "
        "disk, and **? means the result carries no fingerprint at all** and cannot "
        "be checked either way. Re-running the benchmark clears both.",
        "",
    ]
    return "\n".join(out)


def render_readme(root: Path, index: dict[str, Any]) -> Path | None:
    """Writes the standings into bots/README.md, between the markers."""
    readme = Path(root) / "README.md"
    if not readme.is_file():
        return None
    text = readme.read_text(encoding="utf-8")
    begin, end = text.find(README_BEGIN), text.find(README_END)
    if begin < 0 or end < 0:
        return None
    readme.write_text(
        text[:begin] + README_BEGIN + "\n\n" + as_markdown(index) + "\n" + text[end:],
        encoding="utf-8",
    )
    return readme


def format_table(index: dict[str, Any]) -> str:
    rows = index.get("entries") or []
    if not rows:
        return "no bots measured yet"
    head = (f"{'bot':<20}{'category':>10}{'runs':>6}{'badge~':>8}{'badge+':>8}"
            f"{'score~':>9}{'stdev':>8}{'best':>7}{'done':>6}")
    # Said above the table, because this one and `pokelike history` print columns
    # with the same names and mean entirely different things. One is the fixed 50
    # seeds everybody is scored on; the other is whatever you happened to play on
    # this machine. Confusing them is not hypothetical, since the same weights scored
    # 1.60 on 25 seeds picked during development and 1.10 on the official 50.
    out = ["THE OFFICIAL BENCHMARK, the same 50 seeds for everyone, so these "
           "numbers are comparable.", "", head, "-" * len(head)]
    for r in rows:
        v = lambda k: r[k] if r.get(k) is not None else "-"  # noqa: E731
        out.append(
            f"{(r['bot'] or '')[:19]:<20}{(r['category'] or ''):>10}{r['runs'] or 0:>6}"
            f"{v('badges_mean'):>8}{v('badges_best'):>8}{v('score_mean'):>9}"
            f"{v('score_stdev'):>8}{v('score_best'):>7}{v('completed'):>6}"
            + ("  <- code changed since this was measured" if r.get("stale")
               else "  <- no fingerprint: cannot be checked" if r.get("unverified") else "")
        )
    return "\n".join(out)
