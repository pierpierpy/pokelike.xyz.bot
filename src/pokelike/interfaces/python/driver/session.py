"""Starting and stopping a game, so a caller does not have to assemble it.

Two shapes:

    with session() as game:      a script. Closed on the way out, exceptions too.
    game = open_game()           a notebook. Stays alive across cells.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import socket
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ....assets.server import AssetServer
from ....core.game import Game

ROOT = Path(__file__).resolve().parents[5]
SITE = ROOT / "site"


def free_port() -> int:
    """Return a port the OS reports as currently free.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _require_site(site: Path) -> None:
    if not (site / "index.html").is_file():
        raise FileNotFoundError(
            f"the offline copy of the game is missing from {site}.\n"
            "Build it once with:  uv run pokelike setup"
        )


class HostedGame(Game):
    """A Game that also owns the asset server feeding it.

    Calling close() stops both the browser and the server.
    """

    server: AssetServer | None = None

    def close(self) -> None:
        super().close()
        if self.server is not None:
            self.server.stop()
            self.server = None


class _Worker:
    """A thread that owns a game and runs every call to it.

    Playwright's sync API refuses to start inside a running asyncio loop and is
    bound to the thread that created it, so the game lives on a plain thread
    with no event loop. All browser calls are marshalled to that thread.
    """

    def __init__(self) -> None:
        self._calls: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            item = self._calls.get()
            if item is None:
                return
            fn, args, kwargs, fut = item
            try:
                fut.set_result(fn(*args, **kwargs))
            except BaseException as e:  # noqa: BLE001, handed back to the caller
                fut.set_exception(e)

    def run(self, fn, *args, timeout: float = 180.0, **kwargs):
        """Run fn on the owning thread and return the result, with a timeout.
        """
        if not self._thread.is_alive():
            raise RuntimeError("the game thread is gone; open a new game")
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self._calls.put((fn, args, kwargs, fut))
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"{getattr(fn, '__name__', fn)} did not finish within {timeout:.0f}s "
                f"on the game thread. The browser is usually the reason: check that "
                f"`uv run pokelike bot run --bot random --runs 1` works from a terminal."
            ) from None

    def stop(self) -> None:
        self._calls.put(None)
        self._thread.join(timeout=5)


# Game methods that reach into the browser and must run on the owning thread.
# Plain attributes (steps, seed, last_alive) are just data and are read directly.
_BROWSER_CALLS = ("reset", "state", "actions", "step", "reorder", "score",
                  "screenshot", "open", "close")


class ThreadedGame:
    """A HostedGame on its own thread, with the same methods.

    Used automatically when a running event loop is detected (notebooks, async
    contexts). Browser calls are marshalled to the owning thread.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._worker = _Worker()
        self._game: HostedGame = self._worker.run(_build_hosted, **kwargs)

    def __getattr__(self, name: str):
        attr = getattr(self._game, name)
        if name in _BROWSER_CALLS:
            def proxied(*args, **kwargs):
                return self._worker.run(attr, *args, **kwargs)
            return proxied
        return attr

    def close(self) -> None:
        self._worker.run(self._game.close)
        self._worker.stop()

    def __repr__(self) -> str:
        return f"ThreadedGame({self._game!r})"


def _build_hosted(site: Path, watch: bool, load_images: bool,
                  port: int | None) -> HostedGame:
    """Build and open a hosted game. Runs on whichever thread will own it."""
    _require_site(site)
    server = AssetServer(site, port=port or free_port())
    server.start()
    game = HostedGame(url=server.url, watch=watch, load_images=load_images,
                      max_delay=100_000 if watch else 1)
    game.server = server
    try:
        game.open()
    except Exception:
        server.stop()
        raise
    return game


def _loop_is_running() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def open_game(site: Path | str = SITE, watch: bool = False,
              load_images: bool = True, port: int | None = None):
    """Open a game that stays alive until you close it. For notebooks and the REPL.

        game = open_game()
        obs = game.reset(seed=42)
        ...
        game.close()

    Setting `watch=True` opens a visible window with real-time animations.
    """
    kwargs = dict(site=Path(site), watch=watch, load_images=load_images, port=port)
    # A running asyncio loop means Playwright's sync API won't start directly.
    # The ThreadedGame proxy keeps the caller's code identical either way.
    if _loop_is_running():
        return ThreadedGame(**kwargs)
    return _build_hosted(**kwargs)


@contextmanager
def session(site: Path | str = SITE, watch: bool = False,
            load_images: bool = True, port: int | None = None):
    """Context-managed game, closed automatically on exit. For scripts.

        with session() as game:
            obs = game.reset(seed=42)
            while not obs["done"]:
                obs = game.step(0)
    """
    game = open_game(site=site, watch=watch, load_images=load_images, port=port)
    try:
        yield game
    finally:
        game.close()
