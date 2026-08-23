"""HTTP transport: the single model call with retries and token accounting.

Uses urllib with the OpenAI-compatible wire format. No client library dependency.
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
    reasoning_effort: str | None,
    seed: int,
    retries: int,
    token_budget: int,
    tokens_used: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Makes one OpenAI-compatible chat/completions call with retries.

    Returns (message_dict, usage_dict). Raises LLMConfigError for permanent
    failures, LLMError for transient ones, and LLMBudgetError when the token
    budget is spent. When reasoning_effort is not None, the model reasons before
    answering; a provider that rejects the field surfaces its own HTTP error.
    """
    if token_budget and tokens_used >= token_budget:
        raise LLMBudgetError(
            f"run spent {tokens_used} tokens, budget is {token_budget}"
        )
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "temperature": temperature,
        # Best effort: most providers ignore it, none promise determinism.
        "seed": seed,
    }
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        f"{endpoint}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    # Retries with backoff for transient failures (rate limits, 5xx).
    # Auth and model-not-found are not retried because they fail identically forever.
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
