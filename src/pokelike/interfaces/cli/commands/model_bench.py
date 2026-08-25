"""Model benchmark bench and board command handler."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

from ....arena.bench import STANDARD_SEEDS
from ....core.browser import region_name
from ..shared import SITE_ROOT, _server_and_game, llm_settings, parse_seeds
from .docker import _in_docker


def cmd_llm_bench(args) -> int:
    """Runs one or more models against a frozen harness version."""
    from ....harness import llmbench
    from ..shared import validate_region_flags, effective_region

    validate_region_flags(args)
    campaign = getattr(args, "regions", None) is not None
    region = effective_region(args)

    # Required for both `bench` and `board` because rows are never compared across versions.
    known = llmbench.versions()
    if not args.harness:
        print("--harness is required: it decides which frozen harness the model is\n"
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
        # Prices are fetched live because they change, and a cost embedded in a
        # result would go stale.
        price = llmbench.prices()
        if not price:
            print("  (no price list: offline, so no cost column)", file=sys.stderr)
        # Print only the requested version's table.
        table = llmbench.format_table(args.harness, price)
        print()
        print(table or f"  nothing measured yet on harness {args.harness}")
        # The charts are drawn before the README, which embeds the newest one.
        if llmbench.charts_available():
            drawn = llmbench.write_charts()
            if drawn:
                print(f"  charts: {len(drawn)} in {drawn[0].parent}")
        else:
            print("  charts skipped: matplotlib is absent, so run "
                  "`uv sync --group charts` to draw them", file=sys.stderr)
        print(f"\n  all versions: {llmbench.write_readme(price)}")
        # The pages are regenerated here so they cannot drift from the results the
        # table above was printed from.
        pages = llmbench.write_pages(args.harness)
        for kind, paths in pages.items():
            if paths:
                print(f"  {kind}: {len(paths)} page(s) in {paths[0].parent}")
        return 0

    # Only endpoint and key from creds; the model is the thing being measured
    # and arrives per model in the loop below.
    creds = llm_settings(args)
    creds.pop("model", None)

    try:
        settings = llmbench.parse_settings(args.settings)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    if settings:
        # Validate settings against the harness constructor before starting the
        # browser. The constructor names what it refuses.
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

    # A partial seed list (fewer than 50) does not record.
    partial = not llmbench.records(seeds)

    # A harness with cross-run memory cannot be parallelized because splitting
    # seeds across workers gives independent notebooks whose result depends on
    # the partition.
    if args.workers > 1 and llmbench.cross_run_memory(args.harness):
        print(f"harness {args.harness} lets the model keep notes between runs, so "
              f"the runs are not independent\nand the pass cannot be split across "
              f"{args.workers} workers. Run it sequentially: drop --workers.",
              file=sys.stderr)
        raise SystemExit(2)

    # The pre-flight makes one call per model to check tool-call support before
    # spending fifty runs on a model that cannot emit them.
    #
    # Reports rather than raises, because the frozen harness has its own exception
    # classes.
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

        # This prints the estimated cost before committing.
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

    # All passes write their logs and traces into one directory per command.
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
        # Harness-specific settings, recorded because they change the question.
        **({"settings": settings} if settings else {}),
        # The region is included only when it differs from the default (Kanto).
        **({"region": region_name(region)} if region != 1 else {}),
        **({"regions": "all"} if campaign else {}),
        # The endpoint (but never the key) is recorded because which provider served a row matters.
        "endpoint": creds.get("endpoint") or os.environ.get("FW_ENDPOINT") or None,
        "preflight": preflight_said,
    })
    print(f"  writing to {folder}")

    # With multiple workers each owns its own browser; with one worker this
    # process's game is reused.
    server = game = None
    if args.workers <= 1:
        server, game = _server_and_game(args)
    try:
        # The model is the outer loop and the pass is the inner loop, so repeats
        # share the same conditions and the spread between them reflects the
        # model's own variance.
        for model in models:
            for attempt in range(1, args.repeat + 1):
                if args.repeat > 1:
                    print(f"\n  pass {attempt} of {args.repeat}")
                if args.workers > 1:
                    one = llmbench.fan_out(args.harness, model, seeds, args.workers,
                                           SITE_ROOT, port0=args.port + 10,
                                           folder=folder, attempt=attempt,
                                           settings=settings, region=region,
                                           campaign=campaign, **creds)
                else:
                    one = llmbench.play_model(game, args.harness, model, SITE_ROOT,
                                              seeds, folder=folder, attempt=attempt,
                                              conversations=not args.no_conv,
                                              settings=settings, region=region,
                                              campaign=campaign, **creds)
                s = one["summary"]
                print(f"  {model} @ {args.harness}: badges {s.get('badges_mean')} "
                      f"(best {s.get('badges_best')}), "
                      f"{one['tokens_in']:,} in / {one['tokens_out']:,} out tokens, "
                      f"fallback {one['fallback_rate']}, retried {one['retries']}")
                print(f"    log {one.get('log')}")
                print(f"    decisions {one.get('trace')}")
                # Partial or dry runs are not recorded.
                if args.dry_run or partial:
                    why = "--dry-run" if args.dry_run else f"only {len(seeds)} seeds"
                    print(f"    nothing recorded ({why})")
                    continue
                print(f"    recorded in {llmbench.record(args.harness, model, one)}")
            # Print per-model spread when repeating, before committing to
            # the next model's spend.
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
        # Regenerate the readme with prices so cost columns stay populated.
        money = llmbench.prices()
        llmbench.write_readme(money)
        table = llmbench.format_table(args.harness, money)
        if table:
            print(f"\n{table}")
    return 0
