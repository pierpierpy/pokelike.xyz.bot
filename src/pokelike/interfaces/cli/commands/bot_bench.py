"""Bot competition: bench and board commands.

In: parsed args. Out: process exit code.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ....arena.bench import CATEGORIES, STANDARD_SEEDS, format_result, run_benchmark
from ....arena.leaderboard import build_index, format_table, record_result
from ..shared import _server_and_game, add_llm_flags, llm_settings, SITE_ROOT
from .bot_run import BOTS


def cmd_bench(args) -> int:
    """Runs the standard benchmark and writes a submittable result file.

    In: the parsed args. Out: the process exit code.
    """
    from ....bot import LLMBot, create

    try:
        bot = create(args.bot, seed=0, **llm_settings(args))
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
        raise SystemExit(2) from e
    except TypeError as e:
        print(e.args[0], file=sys.stderr)
        raise SystemExit(2) from e

    # A path means the bot is being measured where it lives (inside an
    # experiment folder, usually). That is the point: you benchmark what you are
    # working on without moving it. It is never recorded from there; recording
    # is for bots/, reached by the standard procedure.
    from_path = "/" in args.bot or "\\" in args.bot
    display = (Path(args.bot).resolve().parent.name if args.bot.endswith("bot.py")
               else Path(args.bot).resolve().name) if from_path else args.bot

    seeds = STANDARD_SEEDS[: args.runs] if args.runs else STANDARD_SEEDS

    # Whether this ends in a recorded entry is decided here, before the runs, so
    # the notes below can say what will happen instead of what usually happens.
    partial = len(seeds) < len(STANDARD_SEEDS)
    records = not (args.dry_run or partial or from_path)

    # The one place the two benchmarks get mixed up. Both end up as "an LLM playing
    # the game", and nothing on screen said which question was being answered.
    #
    # Asked of the bot, not of --category. Keyed on the category, the note reached
    # only those who had already understood the difference well enough to pass
    # --category llm. Whoever needs it passes nothing and lands in the default.
    if isinstance(bot, LLMBot):
        print("note: this is the BOT competition, where the model is not held\n"
              "  still: your prompt, view and tools are the submission, and the\n"
              "  model is whatever --model or $MODEL_ID names. To measure a MODEL\n"
              "  against a fixed scaffold, that is `pokelike model bench`.\n")
        if records and args.category != "llm":
            print(f"  it would be recorded under category {args.category!r}, which\n"
                  "  is wrong for a bot that calls a model. Add `--category llm`.\n")

    server, game = _server_and_game(args)
    try:
        result = run_benchmark(
            game, bot, bot_name=args.name or display, site=SITE_ROOT, seeds=seeds,
            author=args.author, category=args.category, description=args.description,
        )
    finally:
        game.close()
        server.stop()

    print(format_result(result))

    # A PARTIAL run does not produce an entry, and neither does --dry-run, which
    # is what `records` above already worked out.
    #
    # This used to write one whatever happened, so a `--runs 5` sanity check left
    # a real submission on disk that the next `git add` would pick up. Refusing
    # is not caution, it is the same rule the leaderboard already states: a score
    # over 5 seeds is not comparable to one over 50, so it is not a submission,
    # and something that is not a submission should not be written as one.
    if not records:
        if from_path:
            print(f"\n  nothing recorded (measured from {args.bot}).")
            print("  When it earns its place, bring it into bots/ the standard")
            print("  way: `pokelike bot new`, or copy your bot.py and artifacts.")
            print("  Then bench it there.")
            return 0
        why = ("--dry-run" if args.dry_run
               else f"only {len(seeds)} of the {len(STANDARD_SEEDS)} standard seeds")
        print(f"\n  nothing recorded ({why}).")
        if partial and not args.dry_run:
            print("  run it without --runs to record a result worth comparing.")
        return 0

    # Recorded INTO the bot's own folder, next to the code that earned it, along
    # with whatever it declared in artifacts() and a fingerprint over both. A
    # score and the thing that produced it cannot then drift apart unnoticed.
    if not args.author:
        # The standings have a column for it. Left empty here, it is empty there,
        # and the fix afterwards is another fifty runs.
        print("note: no --author, so the entry will carry an empty one.\n")

    try:
        d = record_result(args.bot, result, bot, BOTS)
    except Exception as e:  # noqa: BLE001 — the runs are the expensive part
        # Fifty runs took minutes; a failure in the last five seconds must not
        # throw them away. Written somewhere plain, with the one command that
        # files it once whatever broke is fixed.
        from ....arena.bench import save
        from ....bot.catalogue import slugify

        rescue = save(result, BOTS / slugify(args.bot) / "result.unrecorded.json")
        print(f"\n  could not record: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"  the {len(seeds)} runs are NOT lost, they are in {rescue}", file=sys.stderr)
        print("  fix the error, then:  uv run pokelike bot board", file=sys.stderr)
        raise SystemExit(1) from e
    build_index(BOTS)

    rel = d.relative_to(Path.cwd()) if d.is_relative_to(Path.cwd()) else d
    print(f"\n  recorded in {rel}/result.json")
    for f in sorted(d.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            print(f"    {f.relative_to(d)}")
    print("\n  to submit, with origin your fork:")
    print(f"    git checkout -b {result['bot']}")
    print(f"    git add {rel}")
    print(f"    git commit -m 'Add {result['bot']}'")
    print(f"    git push origin {result['bot']}")
    print("    then open the pull request GitHub offers you")
    print("\n  (if you cloned this repo instead of your own fork, origin is not")
    print("   yours to push to: fork it and add that remote first. See CONTRIBUTING.md.)")
    return 0


def cmd_leaderboard(args) -> int:
    """Rebuilds the index from the entries on disk and prints the table.

    In: the parsed args. Out: the process exit code.
    """
    index = build_index(BOTS)
    print(format_table(index))
    print(f"\n  {len(index['entries'])} measured, in {BOTS}/")
    return 0


# ------------------------------------------------------------------ arguments


def bot_bench_args(s) -> None:
    """Registers the arguments for `pokelike bot bench`.

    In: the argparse subparser. Out: None (mutates the parser).
    """
    s.add_argument("--bot", default="random", help="which bot to benchmark")
    s.add_argument("--name", default=None, help="name for the leaderboard (defaults to --bot)")
    s.add_argument("--author", default="", help="your name or github handle")
    s.add_argument("--category", default="other", choices=list(CATEGORIES),
                   help="rules, rl, llm, human or other")
    s.add_argument("--description", default="", help="one line on how it works")
    s.add_argument("--runs", type=int, default=0,
                   help="use only the first N standard seeds. A partial run is a "
                        "practice run: it prints the result and writes no entry")
    s.add_argument("--dry-run", action="store_true",
                   help="play all 50 and print the result, but write no entry")
    add_llm_flags(s)
    s.set_defaults(func=cmd_bench)
