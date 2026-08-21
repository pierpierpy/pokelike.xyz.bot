"""Shared utilities for the CLI: credentials, game startup, seed handling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...assets.server import AssetServer
from ...core.browser import SEED_MAX, normalise_seed
from ...core.game import Game

SITE_ROOT = Path(__file__).resolve().parents[4] / "site"

MISSING_DEPS_HELP = """
The browser downloaded but cannot start: your Linux is missing the system
libraries Chromium needs. This is common on Raspberry Pi, minimal server images
and containers.

Install them, then run `pokelike setup` again:

    sudo apt-get install -y libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
        libasound2t64 libatspi2.0-0t64 libpango-1.0-0 libcairo2 libnss3

On older Ubuntu or Debian, drop the `t64` suffixes. Or let Playwright do it:

    sudo $(which python) -m playwright install-deps chromium

Note the `sudo $(which python)`: plain `sudo playwright` usually fails because
the virtualenv is not on root's PATH."""


# --------------------------------------------------------------- credentials
#
# Three flags, on every command that can end up calling a model: --endpoint,
# --api-key and --model. They override the environment; without them nothing
# changes, so `export FW_ENDPOINT=...` keeps working exactly as before and no
# existing script or fork breaks.
#
# A key on the command line is READABLE BY OTHER USERS of the machine, in `ps`,
# and it lands in your shell history. That is a real cost, so `--api-key` also
# accepts `@path`, reads the file and keeps the key out of both. The environment
# and a file are the safe ways; the literal flag is the convenient one.


def add_llm_flags(parser, with_model: bool = True) -> None:
    """The credential flags, worded the same everywhere they appear."""
    g = parser.add_argument_group(
        "model credentials",
        "override FW_ENDPOINT, FW_TOKEN and MODEL_ID without exporting anything",
    )
    g.add_argument("--endpoint", default=None, metavar="URL",
                   help="OpenAI-compatible base URL, no /v1 (overrides $FW_ENDPOINT)")
    g.add_argument("--api-key", dest="api_key", default=None, metavar="KEY",
                   help="the key, or @path to read it from a file (overrides $FW_TOKEN). "
                        "A literal key is visible in `ps` and saved in shell history")
    if with_model:
        g.add_argument("--model", default=None, metavar="ID",
                       help="model id (overrides $MODEL_ID, unless the bot pins one)")


def llm_settings(args) -> dict[str, str]:
    """What was actually given, ready to hand to a bot's constructor.

    Only non-empty values, and that is the whole point: an absent flag must not
    become an empty string, or it would override the environment with nothing and
    turn a working setup into "FW_TOKEN is required".
    """
    out: dict[str, str] = {}
    if getattr(args, "endpoint", None):
        out["endpoint"] = args.endpoint
    if getattr(args, "model", None):
        out["model"] = args.model
    key = getattr(args, "api_key", None)
    if key:
        # @path reads the file, so the key never appears in argv or in history.
        if key.startswith("@"):
            path = Path(key[1:]).expanduser()
            if not path.is_file():
                print(f"no key file at {path}", file=sys.stderr)
                raise SystemExit(2)
            key = path.read_text(encoding="utf-8").strip()
            if not key:
                print(f"{path} is empty", file=sys.stderr)
                raise SystemExit(2)
        out["token"] = key
    return out


def _own_bridge(name: str | None) -> Path | None:
    """A bridge a bot carries, at `<bot>/artifacts/bridge.js`, or None.

    The state is a projection of the game written by hand in `bridge.js`, so a bot
    that needs the engine to give up something nobody thought to expose has nowhere
    else to do it: no `view()` and no tool can invent data the bridge never read.

    In `artifacts/` and not the folder root, because the leaderboard hashes `bot.py`
    plus everything under `artifacts/`. Putting it there makes the score checkable
    for free, and puts the choice in front of anyone reading the submission.

    Resolves the same way `create()` does, so a path and a unique prefix both work.
    Returns None rather than raising: the bot has already been built by the time
    this is called, so a name that does not resolve here is not a new error.
    """
    if not name:
        return None
    try:
        from ...bot import resolve
        from ...bot.catalogue import folder

        base = Path(name) if ("/" in name or "\\" in name) else folder(resolve(name))
        own = base / "artifacts" / "bridge.js"
        return own if own.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def _server_and_game(args) -> tuple[AssetServer, Game]:
    if not SITE_ROOT.is_dir() or not (SITE_ROOT / "index.html").is_file():
        print(
            f"offline copy missing in {SITE_ROOT}\n"
            "run it once with:  pokelike setup",
            file=sys.stderr,
        )
        raise SystemExit(2)
    server = AssetServer(SITE_ROOT, port=args.port)
    server.start()

    watch = getattr(args, "watch", False)
    # With a window open the animations should run at their own speed, otherwise
    # everything flashes past unseen. Headless squashes them to 1 ms because
    # nobody is watching.
    #
    # Which bridge drives the game, in order of precedence.
    #
    # A benchmark run uses the pair frozen beside its harness: every model under a
    # version has to be asked the same question, and the bridge decides what is in
    # the state at all.
    #
    # A bot may carry its own at `bots/<name>/artifacts/bridge.js`. The state is a
    # projection of the game written by hand, so a bot that wants the engine to
    # give up something nobody thought to expose has nowhere else to do it: no
    # `view()` and no tool can invent data the bridge never read. `artifacts/` and
    # not the folder root, because the leaderboard hashes `bot.py` plus everything
    # under `artifacts/`, so putting it there makes the score checkable for free.
    #
    # `init.js` is deliberately NOT overridable by a bot. It pins Math.random and
    # Date.now, and a run's seed is built from both, so a bot supplying its own
    # would play fifty different games while the table said it had played the
    # standard fifty seeds. More information is fair game and is visible in the
    # fingerprint; a different game under the same seed is not.
    #
    # Everything else gets the shared pair, and should: play and bot follow a fix
    # rather than being pinned away from one.
    scripts = {}
    if getattr(args, "harness", None):
        from ...harness import llmbench as _lb
        scripts = _lb.script_paths(args.harness)
    else:
        own = _own_bridge(getattr(args, "bot", None))
        if own is not None:
            scripts = {"bridge": own}
            print(f"bridge: {own}")
    game = Game(url=server.url, watch=watch, max_delay=100_000 if watch else 1,
                **scripts)
    try:
        game.open()
    except Exception as e:  # noqa: BLE001
        server.stop()
        text = str(e)
        if "missing dependencies" in text or "error while loading shared libraries" in text:
            print("cannot start the browser." + MISSING_DEPS_HELP, file=sys.stderr)
            raise SystemExit(3) from e
        if watch:
            print(
                f"cannot open the window: {e}\n\n"
                "--watch needs the full browser, not just the headless shell:\n"
                "    uv run playwright install chromium",
                file=sys.stderr,
            )
            raise SystemExit(3) from e
        raise
    return server, game


def browser_works() -> tuple[bool, str]:
    """Actually launches the browser. Downloading it is not the same as running it.

    The Playwright installer exits 0 even when it warns that the host is missing
    libraries, so trusting the exit code makes `setup` claim success and every
    later command fail with a stack trace. Better to find out here.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            b.close()
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def seed_arg(value: str) -> int:
    """`--seed` as argparse sees it: refused here rather than after the run.

    The check also lives in `Game.reset`, which is what protects the API and
    anyone using the package as a library. Doing it here as well is what turns
    a traceback into one line, before Chromium has even started.
    """
    try:
        seed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a whole number") from None
    try:
        normalise_seed(seed)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None
    return seed


def parse_seeds(text: str) -> list[int]:
    """`10010,10011` or `10010-10019`, or both mixed, in the order written.

    Order is kept rather than sorted: under a harness that carries notes between
    runs the order IS part of the measurement, so quietly reordering would change
    what was asked for.
    """
    out: list[int] = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            lo, hi = normalise_seed(int(a)), normalise_seed(int(b))
            if hi < lo:
                raise ValueError(f"--seeds {part}: {b} comes before {a}")
            out += list(range(lo, hi + 1))
        else:
            out.append(normalise_seed(int(part)))
    if not out:
        raise ValueError("--seeds needs at least one seed, e.g. --seeds 10010,10011")
    if len(out) != len(set(out)):
        raise ValueError("--seeds lists the same seed twice; every run has to be a "
                         "different game")
    return out
