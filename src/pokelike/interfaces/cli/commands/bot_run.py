"""Bot competition: run and new commands.

In: parsed args. Out: process exit code.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ....core import render
from ....core.browser import SEED_MAX
from ....core.runner import play_run
from ....stats import record
from ..shared import SITE_ROOT, _server_and_game, add_llm_flags, llm_settings, seed_arg

BOTS = Path(__file__).resolve().parents[5] / "bots"


def cmd_bot(args) -> int:
    """Runs a bot: the bot decides the moves, this only drives the loop.

    In: the parsed args. Out: the process exit code.
    """
    from ....bot import create

    try:
        bot = create(args.bot, seed=args.seed, **llm_settings(args))
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
        raise SystemExit(2) from e
    except TypeError as e:
        print(e.args[0], file=sys.stderr)
        raise SystemExit(2) from e

    # Runs walk the seed forward, so a start that is fine on its own can still
    # run off the end part way through. Better to say so now than to stop after
    # the third of ten runs.
    if args.seed + args.runs > SEED_MAX:
        print(f"seed {args.seed} plus {args.runs} runs goes past the engine's "
              f"limit of {SEED_MAX - 1}: start lower.", file=sys.stderr)
        raise SystemExit(2)

    server, game = _server_and_game(args)
    try:
        for i in range(args.runs):
            seed = args.seed + i

            def each_step(obs, steps, _i=i):
                # Before the decision, so you see the board it was taken on.
                if args.graph and obs.get("map"):
                    print(render.graph_view(obs["map"], colour=sys.stdout.isatty(),
                                            emoji=not args.ascii_map), flush=True)
                if args.shots:
                    game.screenshot(
                        Path(args.shots) / f"{_i:02d}-{steps:03d}-{obs['screen']}.png"
                    )
                if args.watch and steps:
                    game.session.page.wait_for_timeout(args.pause)

            # Streamed rather than printed at the end: a run takes tens of
            # seconds, and watching it decide is the point of asking for a log.
            def each_decision(entry):
                print(render.trace_view([entry], detail=args.detailed), flush=True)

            if args.detailed:
                print(f"\n--- run {i + 1}/{args.runs}, seed {seed} ---", flush=True)

            r = play_run(game, bot, seed, max_steps=args.max_steps, on_step=each_step,
                         on_decision=each_decision if args.detailed else None)

            if args.detailed:
                print(render.ending_view(r["final_state"], game.last_alive,
                                         r["score_detail"]), flush=True)

            if not args.no_stats:
                record(bot=args.bot, seed=seed, state=r["final_state"],
                       score=r["score_detail"], steps=r["steps"], alive=game.last_alive,
                       extra=bot.metadata() if hasattr(bot, "metadata") else None)
            # We print `score` (points without the time bonus) because it is the
            # only comparable one: the time bonus is worth ~1000 on a scale where
            # everything else is in the tens.
            print(
                f"run {i + 1}/{args.runs}  seed {seed}  "
                f"steps {r['steps']:>3}  end {r['ending']:<16} "
                f"badges {r['badges']}  score {r['score']}  "
                f"(KO {r['kos']}, faints {r['faints']}, maps {r['maps']})"
            )
        return 0
    finally:
        game.close()
        server.stop()


def cmd_new_bot(args) -> int:
    """Creates a bot folder that already plays, so it can be measured at once.

    In: the parsed args. Out: the process exit code.
    """
    from ....arena.scaffold import new_bot

    try:
        d = new_bot(args.name, BOTS, llm=args.llm)
    except FileExistsError as e:
        print(e, file=sys.stderr)
        raise SystemExit(2) from e

    rel = d.relative_to(Path.cwd()) if d.is_relative_to(Path.cwd()) else d
    slug = d.name
    print(f"created {rel}/\n")
    if args.llm:
        print("  bot.py        a prompt on the shared LLM harness. Rewrite PROMPT.")
    else:
        print("  bot.py        a bot that already plays. Replace what it does.")
    print("  artifacts/    weights, prompts, tables, whatever yours needs")
    print("  README.md     one line on how it decides\n")
    if args.llm:
        print("Point it at a model, then measure it:\n")
        print('  export FW_ENDPOINT="https://..."   # base URL, no /v1')
        print('  export FW_TOKEN="..."')
        print('  export MODEL_ID="..."')
    else:
        print("Try it, then measure it before you change anything:\n")
    print(f"  uv run pokelike bot run --bot {slug} --runs 5 -d")
    print(f"  uv run pokelike bot bench --bot {slug} --dry-run\n")
    print("The whole path from here to a pull request is in CONTRIBUTING.md.")
    return 0


# ------------------------------------------------------------------ arguments


def bot_run_args(s) -> None:
    """Registers the arguments for `pokelike bot run`.

    In: the argparse subparser. Out: None (mutates the parser).
    """
    s.add_argument("--bot", default="random", help="which bot to play: a folder under bots/")
    s.add_argument("--seed", type=seed_arg, default=1)
    s.add_argument("--runs", type=int, default=3)
    s.add_argument("--max-steps", type=int, default=300)
    s.add_argument("--watch", action="store_true", help="open a real window and watch")
    s.add_argument("--shots", metavar="FOLDER", help="save an image at every step")
    s.add_argument("--pause", type=int, default=800, help="ms between moves with --watch")
    s.add_argument("--no-history", "--no-stats", dest="no_stats", action="store_true",
                   help="do not record the runs")
    s.add_argument("-g", "--graph", action="store_true",
                   help="draw the map before each decision, with where you are on it")
    s.add_argument("--ascii-map", action="store_true",
                   help="draw the map with symbols instead of emoji, for terminals "
                        "whose font has no colour emoji")
    s.add_argument("-d", "--detailed", action="count", default=0,
                   help="one line per decision; -dd adds the bot's reasoning, "
                        "-ddd adds the team")
    add_llm_flags(s)
    s.set_defaults(func=cmd_bot)


def bot_new_args(s) -> None:
    """Registers the arguments for `pokelike bot new`.

    In: the argparse subparser. Out: None (mutates the parser).
    """
    s.add_argument("name", help="what to call it, e.g. my-bot")
    s.add_argument("--llm", action="store_true",
                   help="start from the shared LLM harness: you write only the prompt")
    s.set_defaults(func=cmd_new_bot)
