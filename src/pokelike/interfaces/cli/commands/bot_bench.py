"""Bot competition: bench and board commands.

In: parsed args. Out: process exit code.
"""

from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime
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
        # --- logging: same files the model benchmark writes, into the bot's folder
        from ....logging import Conversations, PassLog
        from ....logging.trace import enrich_decision

        # The bot folder: either a path given directly or the standard bots/ location.
        if from_path:
            bot_dir = (Path(args.bot).resolve().parent if args.bot.endswith("bot.py")
                       else Path(args.bot).resolve())
        else:
            from ....bot.catalogue import folder as bot_folder
            bot_dir = bot_folder(args.bot)

        # One directory per bench invocation, timestamped + unique suffix.
        log_base = bot_dir / "log"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        while True:
            log_dir = log_base / f"{ts}-{uuid.uuid4().hex[:4]}"
            try:
                log_dir.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                continue

        stem = "bench-pass1"
        header_lines = [
            f"{datetime.now():%Y-%m-%d %H:%M:%S}  bot {display}",
            f"{len(seeds)} seeds, seeds {seeds[0]}..{seeds[-1]}",
        ]

        def _bot_done_summary(log, one_pass):
            """Summary line for a bot bench pass (no model-specific vocabulary)."""
            s = one_pass.get("summary") or {}
            mins = (time.time() - log.started) / 60
            log._say(
                f"done  {s.get('runs', log.n)} runs  "
                f"{s.get('badges_mean')} badges  "
                f"in {mins:.1f} min"
            )

        log = PassLog(
            version="bot", model=display, seeds=seeds, workers=1,
            folder=log_dir, stem=stem, header_lines=header_lines,
            done_summary=_bot_done_summary,
        )

        # Keep the last observation so the decision enricher can read the map.
        seen: dict = {}
        drawn = [""]

        # Everything the model was given, beside the trace. Wraps the bot's own
        # call_model, so it costs the bot nothing and a bot that talks to no model
        # (the random one, a policy, a search) simply writes no file.
        chat = Conversations(log.path.with_name(log.path.stem + "-chat.jsonl"))
        if not getattr(args, "no_conv", False):
            chat.watch(bot)

        def on_step(obs, steps):
            seen["obs"] = obs
            chat.turn(obs.get("seed", 0), obs.get("steps", 0))

        def on_run(row, done_count, total):
            now = time.time()
            row["secs"] = round(now - _last[0], 1)
            _last[0] = now
            row["order"] = done_count
            # Token counts for LLM bots.
            if hasattr(bot, "metadata"):
                n = bot.metadata()
                row.update(
                    tokens_in=n.get("tokens_in", 0),
                    tokens_out=n.get("tokens_out", 0),
                    calls=n.get("calls", 0),
                    turns=n.get("turns", 0),
                    fallbacks=n.get("fallbacks", 0),
                    retries=n.get("retries", 0),
                )
            log.run(row)

        def on_decision(e):
            chat.flush()
            enriched = enrich_decision(e, bot, seen.get("obs"), drawn)
            log.decision(enriched)

        _last = [time.time()]

        try:
            result = run_benchmark(
                game, bot, bot_name=args.name or display, site=SITE_ROOT, seeds=seeds,
                author=args.author, category=args.category,
                description=args.description,
                on_run=on_run, on_decision=on_decision, on_step=on_step,
            )
        except BaseException:
            chat.close()
            log.close()
            raise

        # Write the done summary using the result.
        chat.close()
        log.done(result)
        log.close()

        print(f"  log {log.path}")
        print(f"  decisions {log.trace_path}")
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
    s.add_argument("--no-conv", action="store_true",
                   help="do not write the conversations file. Every model exchange "
                        "is logged beside the trace by default, which is what you "
                        "read when a decision surprises you; it is also the biggest "
                        "file a pass writes")
    s.add_argument("--dry-run", action="store_true",
                   help="play all 50 and print the result, but write no entry")
    add_llm_flags(s)
    s.set_defaults(func=cmd_bench)
