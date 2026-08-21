"""Pricing, cost estimation, and pre-flight checks for a benchmark pass.

Token counts in and out, per run, never money. Prices change and a measurement
should not rot because a provider ran a promotion, so cost stays a function of
these counts applied whenever it is asked for (from OpenRouter's model list, at
query time).
"""

from __future__ import annotations

import json
import time
from typing import Any

from .versions import _bench, cross_run_memory, harness_path

# Filled by `cached_prices()`: (when it was fetched, the list). Module level so
# every view in one process shares the one fetch.
_PRICE_CACHE: tuple[float, dict[str, dict[str, float]]] | None = None

# Tokens a single run spends, when nothing has been recorded yet to look at.
# Only used to answer "what will this cost me" BEFORE the first pass exists; once
# one does, the real numbers replace it.
TYPICAL_RUN = (30_000, 1_600)


def prices(url: str = "https://openrouter.ai/api/v1/models",
           timeout: float = 10.0) -> dict[str, dict[str, float]]:
    """Fetches per-token USD prices keyed by model id.

    In: an OpenRouter-compatible URL and timeout. Out: dict of model id to
    {in, out} per-token prices, or empty dict on failure.
    """
    # A public endpoint: no key, so this works whatever provider a run actually
    # used. OpenRouter quotes per TOKEN as strings ("0.00000015") and a free
    # model is exactly "0", which is why the column can legitimately read 0.
    #
    # Returns an empty dict rather than raising when there is no network. Cost is a
    # convenience on top of the measurement, and a table that refuses to print
    # because a price list was unreachable would have its priorities backwards.
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
    """The same list as `prices()`, fetched at most once every `ttl` seconds.

    In: how long a fetched list stays good, in seconds. Out: dict of model id to
    {in, out} per-token prices, empty when the list could not be had.
    """
    # For the live views, which redraw every couple of seconds. The price list is
    # somebody else's slowly moving fact, so fetching it per frame would be a
    # request a second for a number that changes monthly. A failed fetch is NOT
    # cached: a machine that was offline picks the list up as soon as it is back,
    # rather than showing dashes for ten minutes.
    global _PRICE_CACHE
    now = time.monotonic()
    if _PRICE_CACHE is not None and now - _PRICE_CACHE[0] < ttl:
        return _PRICE_CACHE[1]
    got = prices()
    if got:
        _PRICE_CACHE = (now, got)
    return got


def cost(tokens_in: int, tokens_out: int, price: dict[str, float] | None) -> float | None:
    """Computes USD for tokens already counted at supplied prices.

    In: token counts in/out and an optional {in, out} price dict. Out: USD or None.
    """
    # Kept as a function of the two counts rather than a field in the result, and
    # that is the whole point: prices are somebody else's changing fact. A cost
    # written into a result would be a claim about what today costs, made months
    # ago, that nobody can correct without re-running a benchmark that has not
    # changed. The tokens are the measurement; money is a view of it.
    if not price:
        return None
    return tokens_in * price.get("in", 0.0) + tokens_out * price.get("out", 0.0)


def estimate(version: str, model: str, n_runs: int,
             price: dict[str, float] | None) -> dict[str, Any]:
    """Estimates what a sweep is about to cost before any of it is spent.

    In: harness version, model id, number of runs, per-token price dict.
    Out: dict with model, runs, basis, token estimates, and USD.
    """
    # Uses the tokens per run actually recorded under this harness (any model's,
    # since the harness is what decides how much text a turn carries) and falls
    # back to a documented guess when the benchmark is empty. Says which it used,
    # because an estimate whose basis is invisible gets quoted as a measurement.
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
        # Not silently scaled up by a guessed factor: that would be an invented
        # number wearing an estimate's clothes. Said out loud instead: a harness
        # that carries notes puts them in every prompt of every turn, so its real
        # input is higher than this until one pass exists to measure.
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
    """One probe call to check whether this model can use tools on this endpoint.

    In: harness version, model id, optional endpoint/token. Out: dict with ok,
    tool_calls, tokens, and why (on failure).
    """
    # The failure this exists for: a model that cannot emit tool calls scores a
    # perfect zero and takes half an hour to do it. Every turn exhausts its rounds,
    # falls back to the safe heuristic, and the run completes looking like a model
    # that plays badly: the only sign being `fallback_rate` at 1.0, read afterwards.
    # Fifty runs, real money, and nothing measured.
    #
    # So: one trivial request with the real tools attached, asking for the one thing
    # the harness cannot do without. Deliberately not a game state: this is not
    # asking whether the model plays well, only whether it can speak the protocol.
    # Costs a few hundred tokens.
    #
    # NEVER RAISES, and that is not laziness. The harness is a frozen copy, so it
    # defines its own `LLMConfigError` under its own module name: a class the
    # package's `except LLMConfigError` does not catch. Anything that reaches out
    # from behind that boundary and expects the caller to recognise it is wrong by
    # construction. So every outcome comes back as data, and the caller has one
    # branch: `ok`.
    from ...bot.catalogue import load_class

    out: dict[str, Any] = {"model": model, "harness": version, "ok": False,
                           "tool_calls": [], "tokens_in": 0, "tokens_out": 0}
    try:
        cls = load_class(harness_path(version))
        bot = cls(seed=0, model=model, endpoint=endpoint, token=token)
    except Exception as e:  # noqa: BLE001 -- a bad endpoint or token lands here
        out["why"] = f"{type(e).__name__}: {e}"
        return out

    # Something with an unambiguous right answer, so a refusal to use the tool is
    # about the model's abilities and not about the question being hard.
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
