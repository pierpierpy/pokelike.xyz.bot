"""Starting and stopping a game, so a caller does not have to assemble it.

Everything was importable and nothing was ready to use: playing one run meant
finding the offline copy, starting an asset server, choosing a port that is free,
opening a browser, and closing both afterwards. Five lines of identical
boilerplate at the top of every script anyone wrote against this repo.

Two shapes, because they are genuinely different situations:

    with session() as game:      a script. Closed on the way out, exceptions too.
    game = open_game()           a notebook. `with` does not span cells, so the
                                 game has to outlive the one that opened it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import socket
import statistics
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ...assets.server import AssetServer
from ...core.game import Game
from ...runner import play_run
from tqdm import tqdm
ROOT = Path(__file__).resolve().parents[4]
SITE = ROOT / "site"


def free_port() -> int:
    """A port the OS says is free, asked for at the moment it is needed.

    Not a constant. A fixed one collides with itself as soon as two scripts run
    at once, or one is left holding the socket, and `Address already in use`
    reads like a bug in the game rather than two things wanting the same number.
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
    """A `Game` that also owns the server feeding it.

    So that `close()` means what a caller expects — put the whole thing away —
    instead of leaving a web server running that nothing will ever stop.
    """

    server: AssetServer | None = None

    def close(self) -> None:
        super().close()
        if self.server is not None:
            self.server.stop()
            self.server = None


class _Worker:
    """A thread that owns a game and runs every call to it.

    Jupyter keeps an asyncio loop running, and Playwright's SYNC api refuses to
    start inside one — it checks `loop.is_running()` and raises, so no amount of
    nest_asyncio helps. The fix is not to fight the loop but to leave it: the
    game is built and driven on a plain thread that has no loop at all.

    Everything goes through this one thread on purpose. Playwright's sync api is
    bound to the thread that created it, so calling it from anywhere else fails
    with `greenlet.error: Cannot switch to a different thread`. It is the same
    constraint that makes the HTTP server single-threaded.
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
            except BaseException as e:  # noqa: BLE001 — handed back to the caller
                fut.set_exception(e)

    def run(self, fn, *args, timeout: float = 180.0, **kwargs):
        """Runs `fn` on the owning thread and returns its result here.

        With a timeout, because without one anything that goes wrong on the
        other thread is an indefinite wait: in a notebook that reads as a cell
        that never finishes and a kernel you end up interrupting, which says
        nothing about what actually happened.
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


# Everything on `Game` that reaches into the browser, and so has to be run on the
# thread that owns it. Plain attributes (`steps`, `seed`, `last_alive`) are just
# data and are read directly.
_BROWSER_CALLS = ("reset", "state", "actions", "step", "reorder", "score",
                  "screenshot", "open", "close")


class ThreadedGame:
    """A `HostedGame` living on its own thread, with the same methods.

    Used automatically when there is a running event loop — a notebook, or any
    async context. Elsewhere the plain object is handed back, since a thread
    would only add a hop.
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
    """Builds and opens a hosted game. Runs on whichever thread will own it."""
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
    """A game that stays open until you close it. For notebooks and the REPL.

    `with` cannot span notebook cells, which is the whole point of a notebook:
    start a run in one cell, take a move in the next, look at the state in the
    one after. So this hands back a live game and leaves closing to you.

        game = open_game()
        obs = game.reset(seed=42)
        ...
        game.close()

    `watch=True` opens a real window and lets the animations play at their own
    speed. Headless they are collapsed to 1 ms, since nobody is looking.
    """
    kwargs = dict(site=Path(site), watch=watch, load_images=load_images, port=port)
    # In a notebook there is a live asyncio loop and Playwright's sync api will
    # not start inside one. Handing back a threaded game keeps this call the same
    # either way, rather than making every notebook user find that out.
    if _loop_is_running():
        return ThreadedGame(**kwargs)
    return _build_hosted(**kwargs)


@contextmanager
def session(site: Path | str = SITE, watch: bool = False,
            load_images: bool = True, port: int | None = None):
    """The same game, closed for you on the way out. For scripts.

        with session() as game:
            obs = game.reset(seed=42)
            while not obs["done"]:
                obs = game.step(0)

    Closed even when the body raises: a leaked browser is what makes the NEXT
    run fail, for reasons that have nothing to do with the change you just made.
    """
    game = open_game(site=site, watch=watch, load_images=load_images, port=port)
    try:
        yield game
    finally:
        game.close()


def play(bot: Any, seed: int = 1, max_steps: int = 400, watch: bool = False,
         on_decision=None, site: Path | str = SITE) -> dict[str, Any]:
    """One run with `bot`, returning what happened, decision trace included.

    The very same `play_run` the CLI and the benchmark use, so a run played from
    here is the same run and is logged the same way.
    """
    with session(site=site, watch=watch) as game:
        return play_run(game, bot, seed, max_steps=max_steps, on_decision=on_decision)


def evaluate(bot: Any, seeds, max_steps: int = 400,
             site: Path | str = SITE) -> list[dict[str, Any]]:
    """`bot` over several seeds in one browser. One row per run."""
    with session(site=site) as game:
        return [play_run(game, bot, s, max_steps=max_steps) for s in seeds]


def compare(bots: dict[str, Any], seeds, baseline: str | None = None,
            site: Path | str = SITE) -> dict[str, Any]:
    """Several bots over the SAME seeds, compared pairwise.

    Paired on purpose. Runs vary enormously by luck here, so two separate means
    mostly measure who drew the nicer maps. The question worth asking is "on this
    identical run, did it do better".

    `baseline` names what everything is measured against; without one a random
    bot is added to play that part.

    Returns `{"runs": {name: [row, ...]}, "table": str}`.
    """
    from ...bot.random_bot import RandomBot

    seeds = list(seeds)
    entrants = dict(bots)
    if baseline is None:
        baseline = "random"
        entrants.setdefault("random", RandomBot(seed=0))
    if baseline not in entrants:
        raise KeyError(f"baseline '{baseline}' is not one of: {', '.join(entrants)}")

    runs: dict[str, list[dict]] = {}
    with session(site=site) as game:
        for name, bot in tqdm(entrants.items()):
            runs[name] = [play_run(game, bot, s) for s in seeds]
    return {"runs": runs, "table": format_comparison(runs, baseline)}


def format_comparison(runs: dict[str, list[dict]], baseline: str) -> str:
    """The paired table, ranked by badges — what the leaderboard ranks by.

    Reports wins, draws, losses and a t statistic rather than only a mean:
    with this much variance between runs, a difference in means on its own says
    very little.
    """
    m = statistics.mean
    base = runs.get(baseline) or []
    head = (f"{'bot':<18}{'badges~':>9}{'badges+':>9}{'score~':>9}"
            f"{'steps~':>8}{'vs ' + baseline:>14}{'t':>8}")
    out = [head, "-" * len(head)]
    for name in sorted(runs, key=lambda k: -m(r["badges"] for r in runs[k])):
        rows = runs[name]
        cell = t_cell = ""
        if base and name != baseline:
            diff = [a["badges"] - b["badges"] for a, b in zip(rows, base)]
            w = sum(1 for d in diff if d > 0)
            losses = sum(1 for d in diff if d < 0)
            cell = f"{w}W-{len(diff) - w - losses}D-{losses}L"
            if len(diff) > 1 and statistics.stdev(diff) > 0:
                t_cell = f"{m(diff) / (statistics.stdev(diff) / len(diff) ** 0.5):.2f}"
        out.append(
            f"{name:<18}{m(r['badges'] for r in rows):>9.2f}"
            f"{max(r['badges'] for r in rows):>9}"
            f"{m(r['score'] or 0 for r in rows):>9.1f}"
            f"{m(r['steps'] for r in rows):>8.1f}{cell:>14}{t_cell:>8}"
        )
    out += ["-" * len(head), "paired on identical seeds; |t| over 2 is worth believing"]
    return "\n".join(out)
