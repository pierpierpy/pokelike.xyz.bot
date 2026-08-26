"""Shared utilities for the CLI: credentials, game startup, seed handling."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ...assets.server import AssetServer
from ...core.browser import REGIONS, SEED_MAX, normalise_region, normalise_seed, region_name
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
# Every command that can call a model takes three flags: --endpoint, --api-key,
# and --model. They override the environment; without them, FW_ENDPOINT/FW_TOKEN/
# MODEL_ID work as before. The --api-key flag also accepts @path to read a
# file, keeping the key out of `ps` and shell history.


def add_llm_flags(parser, with_model: bool = True) -> None:
    """Add --endpoint, --api-key, and optionally --model to a parser."""
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


def load_dotenv() -> list[str]:
    """Read `.env` at the repo root into os.environ using setdefault.

    Returns the names of the variables set, never their values.
    """
    # Uses setdefault so an explicit export always wins over the file.
    root = Path(__file__).resolve().parents[3].parent
    path = root / ".env"
    if not path.is_file():
        return []
    filled = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip()
        # Strip surrounding quotes from the value.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not name or name in os.environ:
            continue
        os.environ[name] = value
        filled.append(name)
    return filled


def llm_settings(args) -> dict[str, str]:
    """Return non-empty credential values from the parsed args.

    Absent flags are omitted so they do not override the environment with empty
    strings.
    """
    out: dict[str, str] = {}
    if getattr(args, "endpoint", None):
        out["endpoint"] = args.endpoint
    if getattr(args, "model", None):
        out["model"] = args.model
    key = getattr(args, "api_key", None)
    if key:
        # @path reads from a file instead.
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
    """Return the path to a bot's own bridge.js at <bot>/artifacts/bridge.js, or None.

    Returns None rather than raising when the name does not resolve.
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
    # With a window open, animations run at real speed; headless squashes them.
    #
    # Bridge precedence:
    # 1. A benchmark run uses the frozen pair beside its harness version.
    # 2. A bot may carry its own at bots/<name>/artifacts/bridge.js.
    # 3. Everything else gets the shared live pair.
    #
    # init.js is not overridable by a bot because it pins Math.random and Date.now,
    # so a custom one would play different games while claiming the standard seeds.
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
    """Launch and immediately close the browser to verify it can start.

    The Playwright installer exits 0 even when system libraries are missing,
    so this is the only reliable check.
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
    """Argparse type for --seed that validates and returns the integer.

    Rejects invalid seeds early, before the browser starts.
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
    """Parse '10010,10011' or '10010-10019' (or both mixed) into a seed list.

    Order is preserved, so quoting the seed list a pass recorded replays that pass in
    the order it was played. A harness that carries notes between runs accumulates
    them as it goes, which is why the order a pass used is recorded rather than
    assumed.
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


# ---------------------------------------------------------------- region flags
#
# The following two flags are mutually exclusive:
#   --region NAME   one of kanto, johto, hoenn, sinnoh (or 1-4). Default kanto.
#   --regions all   play them in sequence, stopping at the first not won.


def region_arg(value: str) -> int:
    """Argparse type for --region that returns a 1-4 integer or raises."""
    try:
        return normalise_region(value if not value.isdigit() else int(value))
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def add_region_flags(parser) -> None:
    """Add --region and --regions to a subcommand parser."""
    g = parser.add_argument_group(
        "region",
        f"which region to play: one of {', '.join(REGIONS)} (or 1-4)",
    )
    g.add_argument("--region", type=region_arg, default=None, metavar="NAME",
                   help=f"one of {', '.join(REGIONS)}, or 1-4. Default kanto")
    g.add_argument("--regions", default=None, metavar="all",
                   help="play all regions in sequence, stopping at the first not won")


def validate_region_flags(args) -> None:
    """Raise SystemExit(2) if --region and --regions are both set, or if
    --regions has a value other than 'all'.
    """
    has_region = getattr(args, "region", None) is not None
    has_regions = getattr(args, "regions", None) is not None
    if has_region and has_regions:
        print("--region and --regions cannot be used together: one picks a single\n"
              "region, the other plays all four in sequence.", file=sys.stderr)
        raise SystemExit(2)
    if has_regions:
        val = args.regions.strip().lower()
        if val != "all":
            print(f"--regions only accepts 'all', got {args.regions!r}.",
                  file=sys.stderr)
            raise SystemExit(2)


def effective_region(args) -> int:
    """Return the region to play (1-4) from the parsed args. Defaults to kanto (1)."""
    if getattr(args, "region", None) is not None:
        return args.region
    return 1
