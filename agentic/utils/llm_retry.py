"""Small, bounded retry helper for temporary LLM rate limits."""

from __future__ import annotations

import math
import os
import re
import time
from typing import Any


_RETRY_PATTERNS = (
    re.compile(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE),
    re.compile(r"retryDelay['\"\s:]+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE),
)


def _transient_delay(error: Exception, default: float = 60.0) -> tuple[float, str] | None:
    message = str(error)
    upper_message = message.upper()
    if "429" in message or "RESOURCE_EXHAUSTED" in upper_message:
        for pattern in _RETRY_PATTERNS:
            match = pattern.search(message)
            if match:
                return float(match.group(1)), "rate limit"
        return default, "rate limit"
    if "503" in message or "UNAVAILABLE" in upper_message:
        return float(os.getenv("ADS_LLM_UNAVAILABLE_RETRY_SECONDS", "10")), "service unavailable"
    return None


def transient_error_message(error: Exception) -> str | None:
    """Return a safe user-facing message for retryable provider failures."""

    transient = _transient_delay(error)
    if transient is None:
        return None
    _, reason = transient
    if reason == "rate limit":
        return "LLM rate limit remained exhausted after retrying."
    return "LLM service remained unavailable after retrying."


def invoke_with_rate_limit_retry(
    model: Any,
    messages: list[Any],
    *,
    label: str = "LLM",
    max_retries: int | None = None,
):
    """Invoke a model and retry only temporary 429 quota-window errors."""

    retries = (
        int(os.getenv("ADS_LLM_RATE_LIMIT_RETRIES", "2"))
        if max_retries is None
        else max_retries
    )
    for attempt in range(retries + 1):
        try:
            return model.invoke(messages)
        except Exception as exc:
            transient = _transient_delay(exc)
            if transient is None or attempt >= retries:
                raise
            delay, reason = transient
            if reason == "service unavailable":
                delay *= 2 ** attempt
            wait_seconds = max(1, min(math.ceil(delay) + 1, 90))
            print(
                f"{label} hit a temporary {reason}; "
                f"retrying in {wait_seconds}s "
                f"({attempt + 1}/{retries})."
            )
            time.sleep(wait_seconds)
