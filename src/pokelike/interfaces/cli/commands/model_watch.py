"""Model benchmark: the watch/dashboard command.

In: parsed args. Out: process exit code.
"""

from __future__ import annotations


def cmd_watch(args) -> int:
    """Follows one pass, from the trace it is already writing.

    In: the parsed args. Out: the process exit code.
    """
    from ....harness.watch import dashboard, monitor, overview

    if args.overview:
        return monitor(version=args.harness, every=args.every)
    if args.all:
        return overview(version=args.harness)
    return dashboard(version=args.harness, once=args.once,
                     stamp=args.stamp, model=args.model, every=args.every)


def model_watch_args(s) -> None:
    """Registers the arguments for `pokelike model watch`.

    In: the argparse subparser. Out: None (mutates the parser).
    """
    from ....harness import llmbench as _lbv
    # Optional here, unlike on `bench` and `board`. Watching is about what is
    # happening rather than about a question being answered, and with nothing
    # said it follows whichever pass was written to last.
    s.add_argument("--harness", default=None,
                   help="follow a pass of this version, one of: "
                        f"{', '.join(_lbv.versions()) or 'none on disk'}. "
                        "Default: whichever was written to last")
    s.add_argument("--once", action="store_true",
                   help="draw it once and exit, instead of following it")
    s.add_argument("--all", action="store_true",
                   help="every pass on this machine, one row each, instead of "
                        "one pass in detail")
    # Which pass, when more than one is running. Without either, it asks; with
    # nothing to ask (a pipe, a script) it follows the newest and says which.
    s.add_argument("--stamp", default=None, metavar="STAMP",
                   help="the log directory to follow, e.g. 20260820-153310. Part "
                        "of the name is enough")
    s.add_argument("--model", default=None, metavar="ID",
                   help="follow the pass playing this model")
    s.add_argument("-o", "--overview", action="store_true",
                   help="every RUNNING pass at once, each with a live progress bar")
    s.add_argument("--every", type=float, default=2.0, metavar="SECS",
                   help="refresh interval for the live views (default 2s)")
    s.set_defaults(func=cmd_watch)
