"""Registry of played runs stored in SQLite (stats/runs.db). One row per run."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[3] / "stats" / "runs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at     TEXT    NOT NULL,
    bot           TEXT    NOT NULL,
    seed          INTEGER NOT NULL,
    steps         INTEGER,
    ending        TEXT,
    completed     INTEGER,
    badges        INTEGER,
    points        INTEGER,   -- without the time bonus: the only comparable one
    points_raw    INTEGER,   -- as the game computes it, time bonus included
    kos           INTEGER,
    faints        INTEGER,
    maps          INTEGER,
    catches       INTEGER,
    damage_dealt  INTEGER,
    max_level     INTEGER,
    team          TEXT,      -- JSON
    extra         TEXT       -- free JSON, for a bot's own notes
);
CREATE INDEX IF NOT EXISTS idx_bot ON runs(bot);
"""


def _connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.executescript(SCHEMA)
    return conn


def record(
    bot: str,
    seed: int,
    state: dict[str, Any],
    score: dict[str, Any] | None,
    steps: int,
    extra: dict[str, Any] | None = None,
    alive: dict[str, Any] | None = None,
    path: Path | None = None,
) -> int:
    """Saves the outcome of a run. Returns the row id.

    `alive` is the last observation taken while the run was still going; the
    engine wipes `state` on the game-over screen, so team and badges come from
    `alive`.
    """
    s = score or {}
    b = s.get("breakdown") or {}
    st = s.get("stats") or {}
    last = alive or state
    run = last.get("run") or state.get("run") or {}

    row = (
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        bot,
        seed,
        steps,
        state.get("screen"),
        1 if state.get("screen") == "win-screen" else 0,
        run.get("badges"),
        s.get("points_no_time"),
        s.get("points"),
        b.get("enemiesKO"),
        b.get("faints"),
        b.get("mapsCleared"),
        st.get("catches"),
        st.get("totalDamageDealt"),
        st.get("highestLevel"),
        json.dumps(last.get("team") or [], ensure_ascii=False),
        json.dumps(extra or {}, ensure_ascii=False),
    )
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (played_at, bot, seed, steps, ending, completed, badges,"
            " points, points_raw, kos, faints, maps, catches, damage_dealt,"
            " max_level, team, extra)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
        return int(cur.lastrowid or 0)


def summary(path: Path | None = None) -> list[dict[str, Any]]:
    """One row per bot, with averages and bests."""
    with _connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT bot,"
            "       COUNT(*)                   AS runs,"
            "       SUM(completed)             AS completed,"
            "       ROUND(AVG(badges), 2)      AS badges_avg,"
            "       MAX(badges)                AS badges_best,"
            "       ROUND(AVG(maps), 2)        AS maps_avg,"
            "       MAX(maps)                  AS maps_best,"
            "       ROUND(AVG(points), 1)      AS score_avg,"
            "       MIN(points)                AS score_worst,"
            "       MAX(points)                AS score_best,"
            "       ROUND(AVG(catches), 1)     AS catches_avg,"
            "       ROUND(AVG(kos), 1)         AS kos_avg,"
            "       ROUND(AVG(faints), 1)      AS faints_avg,"
            "       ROUND(AVG(max_level), 1)   AS level_avg,"
            "       ROUND(AVG(steps), 1)       AS steps_avg"
            " FROM runs GROUP BY bot ORDER BY score_avg DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def recent(n: int = 10, bot: str | None = None, path: Path | None = None) -> list[dict[str, Any]]:
    with _connect(path) as conn:
        conn.row_factory = sqlite3.Row
        if bot:
            rows = conn.execute(
                "SELECT id, played_at, bot, seed, steps, ending, badges, points"
                " FROM runs WHERE bot = ? ORDER BY id DESC LIMIT ?", (bot, n)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, played_at, bot, seed, steps, ending, badges, points"
                " FROM runs ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in rows]


# (key in the dict, heading, width)
COLUMNS = [
    ("bot", "bot", 11),
    ("runs", "runs", 6),
    ("completed", "done", 6),
    ("badges_avg", "badge~", 8),
    ("badges_best", "badge+", 7),
    ("maps_avg", "maps~", 7),
    ("maps_best", "maps+", 7),
    ("score_avg", "score~", 8),
    ("score_worst", "score-", 7),
    ("score_best", "score+", 7),
    ("catches_avg", "catch~", 7),
    ("kos_avg", "KO~", 6),
    ("faints_avg", "faint~", 7),
    ("level_avg", "Lv max~", 8),
    ("steps_avg", "moves~", 7),
]

EXPLANATION = """
WHAT EACH COLUMN MEANS
  ~ = average over runs        + = best reached

  bot        which bot played
  runs       how many runs it played (a run = from the starter to game over)
  done       runs COMPLETED, i.e. reaching the victory screen by beating the
             whole League. These are NOT badges: 0 here with 3 badges means it
             got to three gyms and then died
  badge~ +   gym badges collected. There are 8 per region
  maps~ +    maps cleared: each map is a board of nodes with a boss at the
             bottom, clearing one is worth +50 points
  score~     average score, using the game's own formula:
                 +500  for finishing the run
                 +  5  per enemy knocked out
                 -  10 per Pokemon of yours that faints
                 + 50  per map cleared
                 + 20  per legendary and per shiny on the team
             It excludes the time bonus, which is worth ~1000 and would drown
             out everything else
  score- +   worst and best, to see how consistent it is
  catch~     Pokemon caught (the team holds up to 6)
  KO~        enemy Pokemon knocked out
  faint~     YOUR Pokemon knocked out. At -10 each, this is the line that sinks
             most scores
  Lv max~    level of the highest Pokemon reached on the team
  moves~     how many decisions the bot made before finishing. Battles play
             themselves, so this is the number of forks it faced
"""


def format_summary(rows: list[dict[str, Any]], explain: bool = False) -> str:
    if not rows:
        return "no runs recorded yet"

    head = f"{COLUMNS[0][1]:<{COLUMNS[0][2]}}" + "".join(
        f"{name:>{width}}" for _, name, width in COLUMNS[1:]
    )
    # This header warns the user: the table uses arbitrary seeds and mixed runs,
    # so it is not comparable between bots the way the standings are.
    out = ["practice runs on this machine, on whatever seeds you played, so not "
           "comparable between bots.",
           "", head, "-" * len(head)]
    for r in rows:
        cells = [f"{str(r.get('bot', '')):<{COLUMNS[0][2]}}"]
        for key, _, width in COLUMNS[1:]:
            v = r.get(key)
            cells.append(f"{'-' if v is None else v:>{width}}")
        out.append("".join(cells))

    if explain:
        out.append(EXPLANATION)
    return "\n".join(out)
