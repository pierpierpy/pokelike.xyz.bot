"""Records the golden fingerprints.

    uv run python tests/record_golden.py

Run this only when the game itself has changed (a new release upstream) and you
have checked by hand that the new behaviour is correct. Regenerating the golden
file to make a failing test go green defeats the whole point.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fingerprint import CASES, fingerprint, save_golden  # noqa: E402

from pokelike.assets import AssetServer  # noqa: E402
from pokelike.core.game import Game  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if not (ROOT / "site" / "index.html").is_file():
        print("offline copy missing: run `pokelike setup` first", file=sys.stderr)
        return 2

    data = {}
    with AssetServer(ROOT / "site", port=8552) as s, Game(url=s.url) as g:
        for seed, policy in CASES:
            key = f"{seed}-{policy}"
            print(f"  {key} ...", flush=True)
            data[key] = fingerprint(g, seed, policy)
            print(f"    {data[key]['steps']} steps, {data[key]['points']} points")

    save_golden(data)
    print(f"\nsaved {len(data)} fingerprints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
