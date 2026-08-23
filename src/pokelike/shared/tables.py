"""This module provides small pieces shared by the two standings formatters.

`arena/leaderboard/table.py` (the bots/ standings) and `harness/llmbench/tables.py`
(the llm-bench standings) each decide whether to show a "region" column the same
way, by checking whether at least one row played somewhere other than kanto.
Neither module imports from the other; both import from here.
"""

from __future__ import annotations

from typing import Any


def show_region(rows: list[dict[str, Any]]) -> bool:
    """Returns True when at least one row's region is set and is not kanto.

    A region column is only worth showing when something in the table actually
    played somewhere else. A table where everything is kanto (or region was
    never recorded) shows no such column at all.
    """
    return any(r.get("region") and r["region"] != "kanto" for r in rows)
