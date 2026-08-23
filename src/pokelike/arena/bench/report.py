"""This module formats and saves benchmark results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save(result: dict[str, Any], path: Path) -> Path:
    """Writes a result document to a JSON file and returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return path


def format_result(result: dict[str, Any]) -> str:
    """Formats a benchmark result as a human-readable block."""
    s = result["summary"]
    g = result["game"]
    return "\n".join([
        "",
        "=" * 60,
        f"  {result['bot']}   [{result['category']}]",
        "=" * 60,
        f"  runs            {s.get('runs')}",
        f"  score mean      {s.get('score_mean')}   (stdev {s.get('score_stdev')})",
        f"  score median    {s.get('score_median')}",
        f"  score range     {s.get('score_worst')} .. {s.get('score_best')}",
        f"  badges mean     {s.get('badges_mean')}   best {s.get('badges_best')}",
        f"  maps mean       {s.get('maps_mean')}",
        f"  runs completed  {s.get('completed')}",
        f"  steps mean      {s.get('steps_mean')}",
        "",
        f"  game bundle     {g['file']}  (sha256 {g['sha256']})",
    ])
