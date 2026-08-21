"""Model benchmark: the bench/board command handler.

In: parsed args. Out: process exit code.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

from ....arena.bench import STANDARD_SEEDS
from ..shared import SITE_ROOT, _server_and_game, llm_settings, parse_seeds
from .docker import _in_docker


def cmd_llm_bench(args) -> int:
    """Runs one or more models against a frozen harness version.

    In: the parsed args. Out: the process exit code.
    """
    from ....harness import llmbench

    # Asked of both verbs. A version IS the question a row answers, so neither
    # running nor reading can be done without naming one.
    known = llmbench.versions()
    if not args.harness:
        print("--harness is required: it decides which frozen scaffold the model is\n"
              "asked to play, and rows are never compared across versions.\n"
              f"  on disk: {', '.join(known) or 'none'}",
              file=sys.stderr)
        return 2
    if args.harness not in known:
        print(f"no harness {args.harness} here. On disk: "
              f"{', '.join(known) or 'none'}", file=sys.stderr)
        return 2

    if getattr(args, "docker", False):
        return _in_docker(args)

    if args.table:
        # Fetched now, not stored: prices are somebody else's changing fact, and a
        # cost written into a result would be a claim about today made months ago.
        price = llmbench.prices()
        if not price:
            print("  (no price list: offline, so no cost column)", file=sys.stderr)
        # The version asked for, and no other. Printing every version on disk put
        # the table you wanted between tables you did not ask about.
        table = llmbench.format_table(args.harness, price)
        print()
        print(table or f"  nothing measured yet on harness {args.harness}")
        print(f"\n  all versions: {llmbench.write_readme(price)}")
        return 0

    # Only the endpoint and the key: here the model is not a setting for one bot,
    # it is the thing being measured, and it arrives per model in the loop below.
    creds = llm_settings(args)
    creds.pop("model", None)

    try:
        settings = llmbench.parse_settings(args.settings)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    if settings:
        # Asked of the harness before the browser is up and the pre-flight is paid
        # for. Below the `--table` branch and not above it, because `board` has no
        # such flag at all: reading it there raised AttributeError on a command that
        # was only printing a table.
        #
        # The constructor is what decides, and it names what it refused. Nothing
        # here has a list of settings to check against, which is the point: a
        # harness added tomorrow needs no change on this side.
        from ....bot.catalogue import load_class

        try:
            load_class(llmbench.harness_path(args.harness))(
                seed=0, model="x", endpoint="http://x", token="x", **settings)
        except TypeError as e:
            print(f"harness {args.harness}: {e}", file=sys.stderr)
            print(f"  `--set` reaches the harness, and this one does not take "
                  f"what was passed.", file=sys.stderr)
            return 2
        except Exception:  # noqa: BLE001, anything else is not this flag's business
            pass

    models = [m.strip() for m in (args.models or args.model or "").split(",") if m.strip()]
    if not models:
        print("name at least one model: --model openai/gpt-4o-mini", file=sys.stderr)
        raise SystemExit(2)
    try:
        llmbench.harness_path(args.harness)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        raise SystemExit(2) from e

    if args.seeds:
        try:
            seeds = parse_seeds(args.seeds)
        except ValueError as e:
            print(e, file=sys.stderr)
            raise SystemExit(2) from e
    else:
        seeds = STANDARD_SEEDS[: args.runs] if args.runs else STANDARD_SEEDS

    # Asked of llmbench rather than compared here: it is the one rule whose
    # failure puts an incomparable row in the table looking exactly like a
    # comparable one, so it lives in one place and has a test.
    partial = not llmbench.records(seeds)

    # Checked here, before the pre-flight spends a token, as well as inside
    # `fan_out` where it cannot be bypassed. A harness that carries the model's
    # notes between runs has no independent runs to hand out: splitting fifty seeds
    # over eight workers gives eight separate notebooks, each covering a fraction of
    # the pass, and the result depends on how the seeds were dealt. It would look
    # like an ordinary row.
    if args.workers > 1 and llmbench.cross_run_memory(args.harness):
        print(f"harness {args.harness} lets the model keep notes between runs, so "
              f"the runs are not independent\nand the pass cannot be split across "
              f"{args.workers} workers. Run it sequentially: drop --workers.",
              file=sys.stderr)
        raise SystemExit(2)

    # Asked once per model, before any seed is played. A model that cannot emit a
    # tool call scores zero over fifty runs and takes half an hour to do it, and
    # the only trace is fallback_rate at 1.0 afterwards. A few hundred tokens now
    # instead of a wasted benchmark later.
    #
    # `preflight` reports rather than raises, deliberately: the harness is a frozen
    # copy with its own exception classes, so there is nothing here that could
    # reliably catch what it throws.
    preflight_said: dict[str, str] = {}
    if not args.no_preflight:
        alive = []
        for model in models:
            p = llmbench.preflight(args.harness, model, **creds)
            preflight_said[model] = ("ready: " + ", ".join(p["tool_calls"])
                                     if p["ok"] else f"skipped: {p.get('why', '')[:200]}")
            if p["ok"]:
                print(f"  {model}: ready (called {', '.join(p['tool_calls'])}, "
                      f"{p['tokens_in']}+{p['tokens_out']} tokens)")
                alive.append(model)
            else:
                print(f"  {model}: SKIPPED ({p.get('why', 'unknown')})",
                      file=sys.stderr)
        if not alive:
            print("\nno model passed the pre-flight; nothing to benchmark",
                  file=sys.stderr)
            raise SystemExit(1)
        models = alive

        # What this is about to cost, before it is spent. The one question a
        # progress bar can never answer and the one worth answering first.
        price = llmbench.prices()
        if price:
            total = 0.0
            for model in models:
                e = llmbench.estimate(args.harness, model,
                                      len(seeds) * args.repeat, price.get(model))
                usd = e["usd"]
                total += usd or 0.0
                print(f"    {model}: ~{e['tokens_in'] / 1e6:.1f}M in / "
                      f"{e['tokens_out'] / 1e6:.2f}M out, "
                      + ("free" if usd == 0 else f"about ${usd:.2f}" if usd
                         else "price unknown"))
            if total:
                print(f"    estimated total: about ${total:.2f} "
                      f"({llmbench.estimate(args.harness, models[0], 1, None)['basis']})")

    # One directory for this whole command: every pass of every model writes its
    # log and its decision trace inside it, so `ls -t` lists your commands and
    # `tail -f <dir>/*.log` follows one of them.
    folder = llmbench.session_dir(args.harness)
    llmbench.record_command(folder, {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "harness": args.harness,
        "models": models,
        "runs": len(seeds),
        "seeds": seeds,
        "workers": args.workers,
        "repeat": args.repeat,
        "records": not (args.dry_run or partial),
        # What the harness was told beyond the shared flags. Recorded because a pass
        # with a different setting is answering a different question, and the flags
        # were the one thing nothing wrote down before.
        **({"settings": settings} if settings else {}),
        # The endpoint, never the key: which provider served a row changes what the
        # row means, and is worth having later. A token is worth nothing later.
        "endpoint": creds.get("endpoint") or os.environ.get("FW_ENDPOINT") or None,
        "preflight": preflight_said,
    })
    print(f"  writing to {folder}")

    # In parallel each worker owns its own browser and its own server, so the
    # parent starts neither. One at a time still uses this process's game, which
    # keeps a single run cheap to look at.
    server = game = None
    if args.workers <= 1:
        server, game = _server_and_game(args)
    try:
        # Model outer, pass inner. Repeats of one model back to back share the
        # same conditions (same endpoint load, same hour) which is what makes
        # the spread between them the model's own variance rather than the
        # provider having a bad afternoon halfway through.
        for model in models:
            for attempt in range(1, args.repeat + 1):
                if args.repeat > 1:
                    print(f"\n  pass {attempt} of {args.repeat}")
                if args.workers > 1:
                    one = llmbench.fan_out(args.harness, model, seeds, args.workers,
                                           SITE_ROOT, port0=args.port + 10,
                                           folder=folder, attempt=attempt,
                                           settings=settings, **creds)
                else:
                    one = llmbench.play_model(game, args.harness, model, SITE_ROOT,
                                              seeds, folder=folder, attempt=attempt,
                                              settings=settings, **creds)
                s = one["summary"]
                print(f"  {model} @ {args.harness}: badges {s.get('badges_mean')} "
                      f"(best {s.get('badges_best')}), "
                      f"{one['tokens_in']:,} in / {one['tokens_out']:,} out tokens, "
                      f"fallback {one['fallback_rate']}, retried {one['retries']}")
                print(f"    log {one.get('log')}")
                print(f"    decisions {one.get('trace')}")
                # Same rule as the main benchmark: a partial run is practice by
                # definition, and --dry-run is how you spend a model's tokens
                # without committing to what came out.
                if args.dry_run or partial:
                    why = "--dry-run" if args.dry_run else f"only {len(seeds)} seeds"
                    print(f"    nothing recorded ({why})")
                    continue
                print(f"    recorded in {llmbench.record(args.harness, model, one)}")
            # Said per model rather than at the end, because with repeats this is
            # the number that decides whether any gap to another model is real,
            # and it is worth seeing before committing to the next model's spend.
            if args.repeat > 1 and not (args.dry_run or partial):
                st = llmbench.stats(
                    json.loads(llmbench.result_path(args.harness, model)
                               .read_text(encoding="utf-8")), args.harness)
                print(f"    {st['passes']} passes: {st['badges_mean']} badges "
                      f"±{st['badges_sem']}, spread across passes "
                      f"{st.get('pass_spread')}")
    finally:
        if game is not None:
            game.close()
        if server is not None:
            server.stop()

    if not (args.dry_run or partial):
        # WITH the price list. Without it every `$` and `$/run` cell is written as a
        # dash, and since this regeneration runs at the end of every recorded pass it
        # would silently wipe the money columns that `--table` had just filled in --
        # which it did, three times, before anyone noticed the two paths disagreed.
        money = llmbench.prices()
        llmbench.write_readme(money)
        table = llmbench.format_table(args.harness, money)
        if table:
            print(f"\n{table}")
    return 0
