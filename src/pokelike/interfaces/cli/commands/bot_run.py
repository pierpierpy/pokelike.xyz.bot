"""Bot competition run and new commands."""

from __future__ import annotations

import sys
from pathlib import Path

from ....core import render
from ....core.browser import SEED_MAX
from ....core.runner import play_run
from ....stats import record
from ..shared import SITE_ROOT, _server_and_game, add_llm_flags, llm_settings, seed_arg, \
    add_region_flags, validate_region_flags, effective_region

from ....shared.paths import BOTS  # noqa: F401 (re-exported for callers)


def cmd_bot(args) -> int:
    """Runs a bot by letting the bot decide the moves while this function drives the loop."""
    from ....bot import create
    from ....core.runner import play_campaign
    from ....core.browser import region_name as _rname

    validate_region_flags(args)

    try:
        bot = create(args.bot, seed=args.seed, **llm_settings(args))
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
        raise SystemExit(2) from e
    except TypeError as e:
        print(e.args[0], file=sys.stderr)
        raise SystemExit(2) from e

    campaign = getattr(args, "regions", None) is not None
    region = effective_region(args)

    # Reject early if seed + runs would exceed the engine's 32-bit limit.
    if args.seed + args.runs > SEED_MAX:
        print(f"seed {args.seed} plus {args.runs} runs goes past the engine's "
              f"limit of {SEED_MAX - 1}: start lower.", file=sys.stderr)
        raise SystemExit(2)

    server, game = _server_and_game(args)
    try:
        if campaign:
            # Campaign mode plays all four regions in sequence per seed.
            for i in range(args.runs):
                seed = args.seed + i
                if args.detailed:
                    print(f"\n--- campaign {i + 1}/{args.runs}, seed {seed} ---", flush=True)

                def on_region(done, _i=i):
                    print(f"  {done['region']}: badges {done['badges']}, "
                          f"steps {done['steps']}, {'won' if done['won'] else 'lost'}",
                          flush=True)

                result = play_campaign(game, bot, seed, on_region=on_region)
                print(
                    f"campaign {i + 1}/{args.runs}  seed {seed}  "
                    f"regions {result['regions_cleared']}/{result['regions_played']}  "
                    f"badges {result['badges']}  steps {result['steps']}  "
                    f"end {result['ending']}"
                )
            return 0

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

            # Stream decisions as they happen.
            def each_decision(entry):
                print(render.trace_view([entry], detail=args.detailed), flush=True)

            if args.detailed:
                print(f"\n--- run {i + 1}/{args.runs}, seed {seed} ---", flush=True)

            r = play_run(game, bot, seed, max_steps=args.max_steps, on_step=each_step,
                         on_decision=each_decision if args.detailed else None,
                         region=region)

            if args.detailed:
                print(render.ending_view(r["final_state"], game.last_alive,
                                         r["score_detail"]), flush=True)

            if not args.no_stats:
                record(bot=args.bot, seed=seed, state=r["final_state"],
                       score=r["score_detail"], steps=r["steps"], alive=game.last_alive,
                       extra=bot.metadata() if hasattr(bot, "metadata") else None)
            # Print score without time bonus, because the time bonus is pinned
            # near 1000 and would drown out everything else.
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
    """Creates a bot folder that already plays, ready to be measured."""
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
    """Registers the arguments for `pokelike bot run`."""
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
    add_region_flags(s)
    add_llm_flags(s)
    s.set_defaults(func=cmd_bot)


def bot_new_args(s) -> None:
    """Registers the arguments for `pokelike bot new`."""
    s.add_argument("name", help="what to call it, e.g. my-bot")
    s.add_argument("--llm", action="store_true",
                   help="start from the shared LLM harness: you write only the prompt")
    s.set_defaults(func=cmd_new_bot)
