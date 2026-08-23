"""Pricing, cost estimation, and pre-flight checks for a benchmark pass.

Token counts are recorded per run. Cost is derived at query time from
OpenRouter's model list because stored dollar amounts rot when prices change.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .versions import _bench, cross_run_memory, harness_path

# Filled by `cached_prices()` with a (timestamp, dict) tuple. This is module-level
# so every view in one process shares the one fetch.
_PRICE_CACHE: tuple[float, dict[str, dict[str, float]]] | None = None

# This fallback per-run token estimate is used when no passes have been recorded yet.
TYPICAL_RUN = (30_000, 1_600)


def prices(url: str = "https://openrouter.ai/api/v1/models",
           timeout: float = 10.0) -> dict[str, dict[str, float]]:
    """Fetches per-token USD prices from the OpenRouter model list.

    Returns an empty dict on failure, because cost is a convenience and should
    not block the standings from printing.
    """
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read()).get("data") or []
    except Exception:  # noqa: BLE001 -- offline is a normal state, not an error
        return {}
    out: dict[str, dict[str, float]] = {}
    for m in data:
        p = m.get("pricing") or {}
        try:
            out[m["id"]] = {"in": float(p.get("prompt") or 0),
                            "out": float(p.get("completion") or 0)}
        except (TypeError, ValueError):
            continue
    return out


def cached_prices(ttl: float = 600.0) -> dict[str, dict[str, float]]:
    """Returns the same list as `prices()`, fetched at most once every `ttl` seconds.

    A failed fetch is not cached, so connectivity restored mid-session takes
    effect immediately.
    """
    global _PRICE_CACHE
    now = time.monotonic()
    if _PRICE_CACHE is not None and now - _PRICE_CACHE[0] < ttl:
        return _PRICE_CACHE[1]
    got = prices()
    if got:
        _PRICE_CACHE = (now, got)
    return got


def cost(tokens_in: int, tokens_out: int, price: dict[str, float] | None) -> float | None:
    """Returns USD for the given token counts at the supplied prices, or None."""
    if not price:
        return None
    return tokens_in * price.get("in", 0.0) + tokens_out * price.get("out", 0.0)


def estimate(version: str, model: str, n_runs: int,
             price: dict[str, float] | None) -> dict[str, Any]:
    """Estimates what a pass will cost before any tokens are spent.

    The estimate uses real per-run averages from this harness when available, and
    falls back to the documented TYPICAL_RUN constant otherwise. The returned dict
    reports which basis was used.
    """
    import sys
    _pkg = sys.modules[__package__]
    seen = [r for d in _pkg.load(version) for p in (d.get("passes") or [])
            for r in (p.get("runs") or [])]
    if seen:
        per_in = sum(r.get("tokens_in") or 0 for r in seen) / len(seen)
        per_out = sum(r.get("tokens_out") or 0 for r in seen) / len(seen)
        basis = f"{len(seen)} runs already recorded under {version}"
    else:
        per_in, per_out = TYPICAL_RUN
        basis = "a typical run; nothing recorded under this harness yet"
        # Memory harnesses put notes in every prompt, so real input will be higher.
        if cross_run_memory(version):
            basis += ", which had none of the notes this one puts in every prompt"
    total_in, total_out = round(per_in * n_runs), round(per_out * n_runs)
    return {
        "model": model, "runs": n_runs, "basis": basis,
        "tokens_in": total_in, "tokens_out": total_out,
        "usd": cost(total_in, total_out, price),
    }


def preflight(version: str, model: str, endpoint: str | None = None,
              token: str | None = None) -> dict[str, Any]:
    """Probes whether this model can use tools on this endpoint.

    A model that cannot emit tool calls scores zero across fifty runs because
    every turn falls back to the harness heuristic. This probe costs a few
    hundred tokens and catches that before a full pass is spent. The function
    returns a dict with `ok` as the branch key and never raises.
    """
    from ...bot.catalogue import load_class

    out: dict[str, Any] = {"model": model, "harness": version, "ok": False,
                           "tool_calls": [], "tokens_in": 0, "tokens_out": 0}
    try:
        cls = load_class(harness_path(version))
        bot = cls(seed=0, model=model, endpoint=endpoint, token=token)
    except Exception as e:  # noqa: BLE001 -- a bad endpoint or token lands here
        out["why"] = f"{type(e).__name__}: {e}"
        return out

    # Trivial prompt that has an unambiguous right answer (call the tool).
    probe = [
        {"role": "system", "content": "You are testing a tool call. Do exactly as asked."},
        {"role": "user", "content":
            "There is one legal action, index 0. Call the play tool with index 0 "
            "and any reason. Do not answer in prose."},
    ]
    try:
        msg = bot.call_model(probe)
    except Exception as e:  # noqa: BLE001
        out.update(why=f"{type(e).__name__}: {e}",
                   tokens_in=bot.tokens_in, tokens_out=bot.tokens_out,
                   retries=bot.retries)
        return out

    calls = msg.get("tool_calls") or []
    out.update(
        tool_calls=[c.get("function", {}).get("name") for c in calls],
        tokens_in=bot.tokens_in, tokens_out=bot.tokens_out, retries=bot.retries,
        ok=bool(calls),
    )
    if not calls:
        out["why"] = (
            "answered, but called no tool. The harness ends a turn by calling "
            "play(), so every turn would exhaust its rounds and fall back to the "
            "safe heuristic, fifty runs of our heuristic under the model's name. "
            "Check that this model supports tool calling on this endpoint."
        )
    return out
