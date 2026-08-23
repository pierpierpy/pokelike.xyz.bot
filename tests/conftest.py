"""Shared fixtures.

The browser-backed tests need the offline copy of the game in `site/`. If the copy
is not there the tests are skipped rather than failing, because a fresh clone has no
`site/` until `pokelike setup` has been run.

One browser is started for the whole session and reused. Launching Chromium costs
about a second, and every test would otherwise pay that cost again.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# `experiments/` is a scratch area and mostly untracked, so nothing under tests/
# may depend on it. The root goes on the path only so the example experiment
# stays importable for anyone who wants to run it from here.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def free_port() -> int:
    """Return a port the OS says is free, asked for at the moment it is needed.

    A fixed port collides with itself when two test runs overlap or a killed run
    still holds the socket, causing browser-backed tests to error with
    `Address already in use`.
    """
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


ASSET_PORT = free_port()


def pytest_collection_modifyitems(config, items):
    """Skip the browser tests when the offline copy is missing."""
    if (SITE / "index.html").is_file():
        return
    skip = pytest.mark.skip(reason="offline copy missing: run `pokelike setup`")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def server():
    from pokelike.assets import AssetServer

    if not (SITE / "index.html").is_file():
        pytest.skip("offline copy missing")
    s = AssetServer(SITE, port=ASSET_PORT)
    s.start()
    yield s
    s.stop()


@pytest.fixture(scope="session")
def game(server):
    """A single live game, reused across tests. `reset()` starts a new run."""
    from pokelike.core.game import Game

    g = Game(url=server.url)
    g.open()
    yield g
    g.close()


@pytest.fixture()
def temp_db(tmp_path):
    """An empty stats database, isolated from the real one."""
    return tmp_path / "runs.db"
