"""HTTP transport: the single model call with retries and token accounting.

Why `urllib` and not a client library: the package has two dependencies, and an
LLM bot should not add a third. One wire format, OpenAI-compatible, which nearly
every provider speaks (including Anthropic, through its compatibility endpoint).
A multi-provider abstraction would be more code to maintain and one more place
for two models to be asked subtly different questions.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

from .config import LLMBudgetError, LLMConfigError, LLMError


def call_model_http(
    *,
    messages: list[dict[str, Any]],
    model: str,
    endpoint: str,
    token: str,
    tools: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    seed: int,
    retries: int,
    token_budget: int,
    tokens_used: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Make one OpenAI-compatible chat/completions call with retries.

    Returns (message_dict, usage_dict). Raises LLMConfigError for anything that
    would fail identically forever, LLMError for anything transient, and
    LLMBudgetError when the token budget is spent.

    The caller is responsible for updating its own counters from usage_dict.
    The second element of the tuple is `{"retries": n}` merged with whatever the
    API returned under `usage`, so the caller can tally retries.
    """
    if token_budget and tokens_used >= token_budget:
        raise LLMBudgetError(
            f"run spent {tokens_used} tokens, budget is {token_budget}"
        )
    body = json.dumps({
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "temperature": temperature,
        # Best effort only. Providers that honour it get closer to repeatable
        # runs; most ignore it, and none of them promise it. Nothing here
        # depends on it working (see `reproducible: False` in the artifacts).
        "seed": seed,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{endpoint}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    # Retried, with backoff, for the failures that are transient. A rate limit
    # is not the model failing to answer: counted as a fallback it would show
    # up as the model being bad at the game, and it is the first thing that
    # happens when runs go in parallel.
    #
    # Auth and model-not-found are NOT retried: they fail identically
    # forever, so trying again just wastes the run more slowly.
    answer: dict[str, Any] | None = None
    retry_count = 0
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                answer = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            if e.code in (401, 403):
                raise LLMConfigError(
                    f"HTTP {e.code} from {endpoint}: the endpoint rejected the "
                    f"token.\n  Check FW_TOKEN: a placeholder left in place looks "
                    f"exactly like this.\n  {detail}"
                ) from e
            if e.code == 404:
                raise LLMConfigError(
                    f"HTTP 404 from {endpoint}/v1/chat/completions.\n"
                    f"  Either the endpoint is not an OpenAI-compatible API, or it "
                    f"does not serve MODEL_ID={model!r}.\n  {detail}"
                ) from e
            if e.code in (408, 409, 425, 429, 500, 502, 503, 504) \
                    and attempt < retries:
                retry_count += 1
                time.sleep(min(2 ** attempt, 30) + random.random())
                continue
            raise LLMError(f"HTTP {e.code}: {detail}") from e
        except Exception as e:  # network, timeout, malformed JSON
            if attempt < retries:
                retry_count += 1
                time.sleep(min(2 ** attempt, 30) + random.random())
                continue
            raise LLMError(f"{type(e).__name__}: {e}") from e
    if answer is None:
        raise LLMError("no answer after retries")

    usage = answer.get("usage") or {}
    choices = answer.get("choices") or []
    if not choices:
        raise LLMError("response had no choices")
    message = choices[0].get("message") or {}
    return message, {**usage, "retries": retry_count}
