"""The command line: the parser, and nothing else.

A thin face over `core.game.Game`. No game logic lives here; command bodies
are in `commands/`, shared flags in `shared.py`, and help text in `help.py`.
"""

from __future__ import annotations

import argparse
import signal
import sys

from ...assets.mirror import PHASES
from ...shared.config import DEFAULT_ASSET_PORT
from .help import _FAMILY, _FORMATTER, _boxes, groups_epilog
from .shared import load_dotenv, seed_arg, add_region_flags
from .commands.general import (cmd_api, cmd_mirror, cmd_play, cmd_schema,
                               cmd_setup, cmd_stats)
from .commands.bot import (bot_bench_args, bot_new_args, bot_run_args, cmd_bench,
                           cmd_bot, cmd_leaderboard, cmd_new_bot)
from .commands.model import (cmd_llm_bench, cmd_stop, cmd_watch,
                             model_bench_args, model_board_args,
                             model_stop_args, model_watch_args)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="pokelike",
        usage=argparse.SUPPRESS,
        epilog=groups_epilog(),
        formatter_class=_FORMATTER,
        add_help=False,
    )
    p.add_argument("--port", type=int, default=DEFAULT_ASSET_PORT, help="port of the game-file server")
    # -h/--help still works, it is just not listed: only --port is worth showing.
    p.add_argument("-h", "--help", action="help", help=argparse.SUPPRESS)
    # The grouped listing lives in the epilog, so argparse's own is suppressed.
    sub = p.add_subparsers(dest="command", required=False, metavar="<command>",
                           help=argparse.SUPPRESS)

    s = sub.add_parser("setup")
    s.add_argument("--force", action="store_true", help="rebuild the copy even if present")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("mirror")
    s.add_argument("--phase", choices=list(PHASES), default="all",
                   help="resume from one phase without downloading everything again")
    s.set_defaults(func=cmd_mirror)

    s = sub.add_parser("play")
    s.add_argument("--seed", type=seed_arg, default=1, help="seed of the run")
    s.add_argument("--watch", action="store_true", help="open a real window and watch")
    s.add_argument("--shots", metavar="FOLDER", help="save an image of every screen")
    add_region_flags(s)
    s.set_defaults(func=cmd_play)

    s = sub.add_parser("api")
    s.add_argument("--api-port", type=int, default=8423)
    s.add_argument("--seed", type=seed_arg, default=1, help="seed of the initial run")
    s.set_defaults(func=cmd_api)

    # ---- the competition: your code is the entry -------------------------------
    fam = sub.add_parser(
        "bot", usage=argparse.SUPPRESS, add_help=False, formatter_class=_FORMATTER,
        epilog=_boxes([("pokelike bot", _FAMILY["pokelike bot"])]),
    )
    fam.add_argument("-h", "--help", action="help", help=argparse.SUPPRESS)
    bots = fam.add_subparsers(dest="verb", required=False, metavar="<verb>",
                              help=argparse.SUPPRESS)
    fam.set_defaults(func=lambda a, _p=fam: _p.print_help() or 0)
    bot_new_args(bots.add_parser("new", help="write a bot folder that already plays"))
    bot_run_args(bots.add_parser("run", help="play it and watch the decisions"))
    bot_bench_args(bots.add_parser(
        "bench", help="the 50 standard seeds, records a result",
        description="Plays the standard fifty seeds and writes bots/<name>/result.json. "
                    "The scaffold is whatever you wrote, so this ranks ideas.",
    ))
    bots.add_parser("board", help="the standings").set_defaults(func=cmd_leaderboard)

    # ---- the model benchmark: the model is the entry ---------------------------
    fam = sub.add_parser(
        "model", usage=argparse.SUPPRESS, add_help=False, formatter_class=_FORMATTER,
        epilog=_boxes([("pokelike model", _FAMILY["pokelike model"])]),
    )
    fam.add_argument("-h", "--help", action="help", help=argparse.SUPPRESS)
    models = fam.add_subparsers(dest="verb", required=False, metavar="<verb>",
                                help=argparse.SUPPRESS)
    fam.set_defaults(func=lambda a, _p=fam: _p.print_help() or 0)
    model_bench_args(models.add_parser(
        "bench", help="a model against one frozen harness version"))
    model_board_args(models.add_parser(
        "board", help="what has been measured, per version"))
    model_stop_args(models.add_parser(
        "stop", help="end a running pass, keeping everything it wrote",
        description="Asks the pass to finish, the way `docker stop` and Ctrl-C do: "
                    "the browser closes, the log is flushed, and the logs, trace "
                    "and notebook stay exactly where they are. Nothing is deleted.",
    ))
    model_watch_args(models.add_parser(
        "watch", help="follow a pass while it plays",
        description="Redraws what the model is doing from the trace the pass is "
                    "already writing: the runs it has finished, where it is now, "
                    "the tools it called this turn and what it has in memory.",
    ))

    s = sub.add_parser("schema")
    s.add_argument("--json", action="store_true", help="print a real observation instead")
    s.add_argument("--markdown", action="store_true",
                   help="regenerate the state reference inside STATE.md")
    s.set_defaults(func=cmd_schema)

    # `history`: what you played on this machine.
    s = sub.add_parser("history")
    s.add_argument("-d", "--explain", action="store_true",
                   help="explain what each column means")
    s.add_argument("--recent", type=int, default=0, help="also show the last N runs")
    s.add_argument("--bot", default=None, help="filter the recent list by bot")
    s.set_defaults(func=cmd_stats)

    args = p.parse_args(list(argv) if argv is not None else sys.argv[1:])

    # Load credentials from `.env` at the repo root without overriding exports.
    # Called here so every command (and every harness bot reading FW_ENDPOINT /
    # FW_TOKEN / MODEL_ID from os.environ) picks them up.
    load_dotenv()

    # Bare `pokelike` with no command shows help.
    if not hasattr(args, "func"):
        p.print_help()
        return 0

    # SIGTERM becomes SystemExit so it unwinds through context managers that
    # close the browser. Ctrl-C prints one line rather than a traceback.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
